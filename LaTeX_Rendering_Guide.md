# LaTeX Rendering Service - Setup Guide & Best Practices

## 🎯 Overview

This project uses a robust offline pre-processing architecture to handle LaTeX rendering. This ensures the live Telegram bot is fast, reliable, and does not perform complex, error-prone rendering tasks in real-time.

**The workflow is:**
1.  An offline Python script (`scripts/preprocess_questions.py`) finds all questions in the database containing LaTeX.
2.  It uses a `pdflatex` -> PDF -> PNG pipeline to generate high-quality images for each question.
3.  These images are uploaded to an S3 bucket.
4.  The database is updated with the S3 URL for each rendered question.
5.  The live bot simply fetches the question and sends the pre-rendered image URL if it exists.

## 🔧 Installation & Dependencies

This setup requires dependencies on the machine that will run the pre-processing script (e.g., your `adaptive-bot-v2` EC2 instance).

### Required System Dependencies

```bash
# For Debian/Ubuntu
sudo apt-get update
sudo apt-get install -y texlive-latex-base texlive-latex-extra texlive-fonts-recommended imagemagick

# For Windows (using Chocolatey)
choco install miktex imagemagick

# For macOS (using Homebrew)
brew install --cask mactex imagemagick
```

### Python Dependencies

Ensure these are in your `requirements.txt` for the pre-processing environment:
```
boto3
sqlalchemy
psycopg2-binary
python-dotenv
pillow
```

## 🚀 How to Use

1.  **Configure `.env`**: Ensure your `.env` file contains the correct `DATABASE_URL` and AWS credentials.
2.  **Run the Pre-processor**: Execute the script from the project root:
    ```bash
    python scripts/preprocess_questions.py
    ```
    *   Use `python scripts/preprocess_questions.py --limit 10` to test with a small batch.
    *   Use `python scripts/preprocess_questions.py --dry-run` to see what questions would be processed without actually rendering them.
3.  **Run the Live Bot**: Once pre-processing is complete, you can run the live bot, which will now serve the images.

## 📋 AWS S3 IAM Policy

Ensure the IAM Role/User for the pre-processing script has the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowObjectActions",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:PutObjectAcl",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::your-bucket-name/rendered-questions/*"
        },
        {
            "Sid": "AllowBucketListing",
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::your-bucket-name"
        }
    ]
}
```

## 🐛 Troubleshooting

- **`pdflatex not found` or `convert not found`**: Ensure TeX Live and ImageMagick are installed and their `bin` directories are in your system's PATH.
- **S3 Permission Errors**: Double-check your IAM policy and ensure your `.env` credentials are correct.
- **Rendering Failures**: Check the `preprocessing.log` file for detailed error messages from the LaTeX engine.