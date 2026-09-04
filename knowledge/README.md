# Knowledge Workspace

This folder is the local staging area for documents you want to use with RuleFinder uploads and optional OpenAI `file_search`.

Suggested layout:

- `knowledge/rules/`: source rulebooks, SRDs, supplements, and adjudication notes
- `knowledge/templates/`: document templates, prompt specs, and drafting skeletons
- `knowledge/examples/`: worked examples, sample outputs, and gold-standard documents
- `knowledge/uploads/`: temporary files you plan to upload into the app

Recommended workflow:

1. Place your source documents into the appropriate folder.
2. Upload the same files through the app when you want them indexed in Postgres/pgvector.
3. If you are using OpenAI hosted `file_search`, upload the relevant files from these folders into your OpenAI vector store as well.

Notes:

- Keep copyrighted or licensed materials private unless you have permission to share them.
- The actual document files are ignored by git; only this folder structure is tracked.
