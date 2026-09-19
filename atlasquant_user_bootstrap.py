"""Offline bootstrap helper for the first AtlasQuant USER/SALES/ADMIN account.

Run locally. It never calls GitHub, Render, Streamlit Cloud or a broker.
The output contains only a PBKDF2 password hash suitable for ATLASQUANT_USERS_JSON.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys

from atlasquant_account_portal import build_provisioning_record, provisioning_json

def generate_record(username:str,role:str,password:str,confirm:str)->str:
    if password!=confirm:
        raise ValueError("password confirmation mismatch")
    record=build_provisioning_record(username,role,password,active=True)
    return provisioning_json(record)

def main(argv=None)->int:
    parser=argparse.ArgumentParser(description="Generate an AtlasQuant hashed user record.")
    parser.add_argument("--username",required=True)
    parser.add_argument("--role",choices=("USER","SALES","ADMIN"),default="USER")
    args=parser.parse_args(argv)
    password=getpass.getpass("Senha: ")
    confirm=getpass.getpass("Confirmar senha: ")
    try:
        output=generate_record(args.username,args.role,password,confirm)
    except Exception as exc:
        print("Falha ao gerar registro: "+str(exc),file=sys.stderr)
        return 2
    print(output)
    print("\nA senha em texto puro não foi salva. Mescle este registro em ATLASQUANT_USERS_JSON.",file=sys.stderr)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
