# Product photos

Put one photo per product here, named after its product ID: `ut-001.jpg`, `ut-045.png`, ...
See `manifest.csv` (run `make product-manifest`) for every ID with its product name.

Then run `make product-images` (local) or `make product-images-cloud` (Cloud SQL + Cloud Storage).
Products without a photo keep the generated flat-lay. Plain white or transparent backgrounds look best.
Customers can't upload product photos; this folder is the only way in.
