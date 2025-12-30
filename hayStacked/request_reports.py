#!/usr/bin/env python3
import os,glob,datetime,time
import base64,json
import hashlib,struct

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import ec
from os.path import dirname, join, abspath

from sqlalchemy import text

from hayStacked.pypush_gsa_icloud import generate_anisette_headers, reset_headers

retryCount = 0

def getKeysDir():
    return abspath(os.path.join('hayStacked', 'keys'))

def sha256(data):
    digest = hashlib.new("sha256")
    digest.update(data)
    return digest.digest()

def decrypt(enc_data, algorithm_dkey, mode):
    decryptor = Cipher(algorithm_dkey, mode).decryptor()
    return decryptor.update(enc_data) + decryptor.finalize()

def decode_tag(data):
    latitude = struct.unpack(">i", data[0:4])[0] / 10000000.0
    longitude = struct.unpack(">i", data[4:8])[0] / 10000000.0
    confidence = int.from_bytes(data[8:9], 'big')
    status = int.from_bytes(data[9:10], 'big')
    return {'lat': latitude, 'lon': longitude, 'conf': confidence, 'status':status}

def getAuth(authFile):
    print("Searching for auth.json at:", authFile)
    if os.path.exists(authFile):
        with open(authFile, "r") as f: j = json.load(f)
        return (j['dsid'], j['searchPartyToken'])
    else:
        raise Exception("Please provide auth.json")


def request_reports(anisette, database, authFile, keysDir, hours=24):
    global retryCount

    try:
        try:
            sqla = database.connect()
        except Exception as e:
            print("Error connecting to local database. Is it in use?")
            print("SQLAlchemy error: ", e)

        privkeys = {}
        names = {}
        for keyfile in glob.glob(join(keysDir, '*.keys')):
            # read key files generated with generate_keys.py
            print("Located key file at:", keyfile)
            with open(keyfile) as f:
                hashed_adv = priv = ''
                name = os.path.basename(keyfile)[0:-5]
                for line in f:
                    key = line.strip().split(': ')
                    if key[0] == 'Private key': priv = key[1]
                    elif key[0] == 'Hashed adv key': hashed_adv = key[1]

                if priv and hashed_adv:
                    privkeys[hashed_adv] = priv
                    names[hashed_adv] = name
                else: print(f"Couldn't find key pair in {keyfile}")

        unixEpoch = int(time.time())
        startdate = unixEpoch - (60 * 60 * hours)
        data = { "search": [{"startDate": startdate *1000, "endDate": unixEpoch *1000, "ids": list(names.keys())}] }

        r = requests.post("https://gateway.icloud.com/acsnservice/fetch",
                auth=getAuth(authFile),
                headers=generate_anisette_headers(),
                json=data)
        print(r)
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            if r.status_code == 401:
                if retryCount < 3:
                    reset_headers()
                    retryCount += 1
                    return request_reports(anisette, database, authFile, keysDir, hours)
                else:
                    print("Request_reports unable to start anisette, 401")
                    anisette.terminate()
                    return None
            else:
                print(f"HTTP error: {e}")
        res = json.loads(r.content.decode())['results']
        print(f'{r.status_code}: {len(res)} reports received.')

        ordered = []
        found = set()
        for report in res:
            priv = int.from_bytes(base64.b64decode(privkeys[report['id']]), 'big')
            data = base64.b64decode(report['payload'].replace('\n', '').replace('\r', ''))
            if len(data) > 88: data = data[:4] + data[5:]

            # the following is all copied from https://github.com/hatomist/openhaystack-python, thanks @hatomist!
            timestamp = int.from_bytes(data[0:4], 'big') +978307200
            if timestamp >= startdate:
                eph_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP224R1(), data[5:62])
                shared_key = ec.derive_private_key(priv, ec.SECP224R1()).exchange(ec.ECDH(), eph_key)
                symmetric_key = sha256(shared_key + b'\x00\x00\x00\x01' + data[5:62])
                decryption_key = symmetric_key[:16]
                iv = symmetric_key[16:]
                enc_data = data[62:72]
                tag = data[72:]

                decrypted = decrypt(enc_data, algorithms.AES(decryption_key), modes.GCM(iv, tag))
                tag = decode_tag(decrypted)
                tag['timestamp'] = timestamp
                tag['isodatetime'] = datetime.datetime.fromtimestamp(timestamp).isoformat()
                tag['key'] = names[report['id']]
                tag['goog'] = 'https://maps.google.com/maps?q=' + str(tag['lat']) + ',' + str(tag['lon'])
                found.add(tag['key'])
                ordered.append(tag)
        print(f'{len(ordered)} reports used.')
        ordered.sort(key=lambda item: item.get('timestamp'))
        print("Found reports:")
        for rep in ordered: print(f"('{rep['key']}', {rep['timestamp']}, '{rep['isodatetime']}', '{rep['lat']}', '{rep['lon']}', '{rep['goog']}', {rep['status']}, {rep['conf']})")

        parameters_to_insert = []
        for rep in ordered:
            parameters_to_insert.append({
                'bike_id': rep['key'],
                'timestamp': rep['timestamp'],
                'latitude': rep['lat'],
                'longitude': rep['lon']
            })

        if parameters_to_insert:
            sqla.execute(
                text("INSERT OR REPLACE INTO location (bike_id, timestamp, latitude, longitude) VALUES (:bike_id, :timestamp, :latitude, :longitude)"),
                parameters_to_insert
            )

        print(f'found:   {list(found)}')
        print(f'missing: {[key for key in names.values() if key not in found]}')
        sqla.commit()
        sqla.close()
        retryCount = 0
    except Exception as e:
        print("Error getting reports:")
        raise e
    finally:
        anisette.terminate()