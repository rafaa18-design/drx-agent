#!/usr/bin/env python3
"""CLI tool for generating bcrypt password hashes.

Usage:
    uv run scripts/hash_password.py
    uv run scripts/hash_password.py --password mypassword
    uv run scripts/hash_password.py --verify '$2b$12$...' --password mypassword
"""

import argparse
import getpass
import sys


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password to hash.

    Returns:
        Bcrypt hash string.
    """
    import bcrypt

    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash.

    Args:
        password: Plain text password to verify.
        password_hash: Bcrypt hash to verify against.

    Returns:
        True if password matches, False otherwise.
    """
    import bcrypt

    return bcrypt.checkpw(
        password.encode('utf-8'),
        password_hash.encode('utf-8'),
    )


def main():
    parser = argparse.ArgumentParser(
        description='Generate or verify bcrypt password hashes',
        epilog='Example: uv run scripts/hash_password.py --password mypassword',
    )
    parser.add_argument(
        '--password',
        '-p',
        help='Password to hash (will prompt if not provided)',
    )
    parser.add_argument(
        '--verify',
        '-v',
        metavar='HASH',
        help='Verify password against existing hash',
    )
    parser.add_argument(
        '--json',
        '-j',
        action='store_true',
        help='Output in JSON format for AUTH_USERS',
    )
    parser.add_argument(
        '--username',
        '-u',
        default='admin',
        help='Username for JSON output (default: admin)',
    )

    args = parser.parse_args()

    # Get password
    if args.password:
        password = args.password
    else:
        password = getpass.getpass('Enter password: ')
        if not args.verify:
            confirm = getpass.getpass('Confirm password: ')
            if password != confirm:
                print('Error: Passwords do not match', file=sys.stderr)
                sys.exit(1)

    if not password:
        print('Error: Password cannot be empty', file=sys.stderr)
        sys.exit(1)

    # Verify or hash
    if args.verify:
        if verify_password(password, args.verify):
            print('✓ Password matches!')
            sys.exit(0)
        else:
            print('✗ Password does not match', file=sys.stderr)
            sys.exit(1)
    else:
        hashed = hash_password(password)
        if args.json:
            import json

            auth_users = {args.username: hashed}
            print(f"AUTH_USERS='{json.dumps(auth_users)}'")
        else:
            print(f'Hash: {hashed}')
            print()
            print('To use in .env file:')
            print(f'AUTH_USERS=\'{{"{args.username}": "{hashed}"}}\'')


if __name__ == '__main__':
    main()
