"""Retired unsafe one-off publisher. Use the versioned create-only LMS ingest client."""

def main():
    raise RuntimeError("Legacy direct SQL publication is retired; use beekip_uploader with DOCUMENT_INGEST_TOKEN")

if __name__ == "__main__":
    main()
