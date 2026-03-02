#!/usr/bin/env python3
"""Generate a Fernet encryption key for broker credential encryption."""

from cryptography.fernet import Fernet


def main():
    key = Fernet.generate_key().decode()
    print("Generated Fernet encryption key:\n")
    print(f"  ENCRYPTION_KEY={key}\n")
    print("Add this to your .env file.")
    print("WARNING: If you change this key, all existing encrypted credentials become unreadable.")


if __name__ == "__main__":
    main()
