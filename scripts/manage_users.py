#!/usr/bin/env python3
import argparse
import binascii
import getpass
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arcade_scanner.database import user_db
from arcade_scanner.models.user import User


def read_new_password(username: str, label: str = "password") -> str | None:
    """Fragt ein Passwort zweimal ab. None heisst: nicht weitermachen.

    Ein leeres Passwort wurde vorher angenommen -- zweimal Enter genuegte, und
    das Konto war ohne Passwort angelegt. Beide Eingaben waren ja gleich.
    """
    password = getpass.getpass(f"Enter {label} for {username}: ")
    confirm = getpass.getpass(f"Confirm {label} for {username}: ")

    if password != confirm:
        print("❌ Passwords do not match.")
        return None
    if not password:
        print("❌ Password cannot be empty.")
        return None
    return password


def password_from_args(args, username: str, label: str = "password") -> str | None:
    if args.password is None:
        return read_new_password(username, label)
    if not args.password:
        print("❌ Password cannot be empty.")
        return None
    print(
        "⚠️  Das Passwort stand auf der Kommandozeile. Es steht damit in der\n"
        "    Shell-History und war waehrend des Aufrufs in `ps` sichtbar."
    )
    return args.password


def list_users(args):
    users = user_db.get_all_users()
    print(f"\n👥 Registered Users ({len(users)}):")
    print(f"   {'-'*30}")
    print(f"   {'Username':<15} | {'Admin':<5}")
    print(f"   {'-'*30}")
    for u in users:
        admin_flag = "Yes" if u.is_admin else "No"
        print(f"   {u.username:<15} | {admin_flag:<5}")
    print("\n")

def add_user(args):
    username = args.username.strip()
    if not username:
        print("❌ Username cannot be empty.")
        return

    if user_db.get_user(username):
        print(f"❌ User '{username}' already exists.")
        return

    password = password_from_args(args, username)
    if password is None:
        return

    salt = os.urandom(16)
    pwd_hash = user_db.hash_password(password, salt)

    new_user = User(
        username=username,
        password_hash=binascii.hexlify(pwd_hash).decode('ascii'),
        salt=binascii.hexlify(salt).decode('ascii'),
        is_admin=args.admin
    )

    user_db.add_user(new_user)
    print(f"✅ User '{username}' created successfully.")

def change_password(args):
    username = args.username.strip()
    user = user_db.get_user(username)

    if not user:
        print(f"❌ User '{username}' not found.")
        return

    password = password_from_args(args, username, "NEW password")
    if password is None:
        return

    salt = os.urandom(16)
    pwd_hash = user_db.hash_password(password, salt)

    user.password_hash = binascii.hexlify(pwd_hash).decode('ascii')
    user.salt = binascii.hexlify(salt).decode('ascii')

    user_db.add_user(user)
    print(f"✅ Password for '{username}' updated successfully.")
    print(
        "ℹ️  Laufende Sitzungen bleiben gueltig. Der Server haelt sie im "
        "Arbeitsspeicher;\n    dieses Skript laeuft in einem eigenen Prozess "
        "und erreicht sie nicht.\n    Wer bereits angemeldet ist, bleibt es -- "
        "bis zum Sitzungsablauf oder\n    einem Neustart des Servers."
    )

def main():
    parser = argparse.ArgumentParser(description="Arcade User Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List Command
    subparsers.add_parser("list", help="List all users")

    # Add Command
    add_parser = subparsers.add_parser("add", help="Add a new user")
    add_parser.add_argument("username", help="Username")
    add_parser.add_argument("--password", help="Password (prompted if omitted)")
    add_parser.add_argument("--admin", action="store_true", help="Grant admin privileges")

    # Passwd Command
    pwd_parser = subparsers.add_parser("passwd", help="Change user password")
    pwd_parser.add_argument("username", help="Username")
    pwd_parser.add_argument("--password", help="New Password (prompted if omitted)")

    args = parser.parse_args()

    if args.command == "list":
        list_users(args)
    elif args.command == "add":
        add_user(args)
    elif args.command == "passwd":
        change_password(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
