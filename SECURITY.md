# Security Policy

## Overview

The ProjectX Python SDK provides access to trading functionality and financial data. We take security seriously and are committed to ensuring the SDK is secure for all users. This document outlines our security practices and how to report vulnerabilities.

## Supported Versions

We currently provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 4.0.x   | :white_check_mark: |
| 3.5.x   | :white_check_mark: (critical fixes only) |
| 3.1.x   | :x:                |
| 3.0.x   | :x:                |
| 2.0.x   | :x:                |
| 1.x.x   | :x:                |

Note: Version 4.0.0 is the current major release (TopstepX-only Gateway). Version 3.1.1 marked the transition to stable production status. Version 3.0.0 introduced TradingSuite. Version 2.0.0 was a complete rewrite with an async-only architecture.

## Reporting a Vulnerability

If you discover a security vulnerability within the ProjectX Python SDK, please follow these steps for responsible disclosure:

1. **DO NOT** disclose the vulnerability publicly or on GitHub issues
2. Send an email to security@projectx.com with:
   - A description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested mitigations (optional)
3. Allow us reasonable time to address the issue before public disclosure

## What to Expect

After submitting a security vulnerability:

- We will acknowledge receipt of your report within 48 hours
- We will provide a more detailed response within 7 days indicating next steps
- We will work with you to understand and address the issue
- We will keep you informed about our progress
- We will credit you when we publish the vulnerability (unless you prefer to remain anonymous)

## Security Update Process

When security vulnerabilities are discovered:

1. We assess the severity and impact
2. We develop and test a fix
3. We release a security update with appropriate version bump
4. We publish a security advisory through GitHub's security advisories feature
5. For critical issues, we may directly notify users who have provided contact information

## Best Practices for SDK Users

To ensure secure use of the ProjectX Python SDK:

### Authentication & API Keys

- Store API keys and credentials securely using environment variables or secure vaults
- Never commit API keys to version control
- Use the recommended config file path (`~/.config/projectx/config.json`) with appropriate file permissions
- Regularly rotate your API keys

### Network Security

- Use HTTPS connections to the API (default in the SDK)
- Consider implementing IP restrictions if supported by your broker or trading platform
- Monitor for unusual API activity

### Dependency Management

- Regularly update the SDK to the latest version
- Use dependency scanning tools to ensure all dependencies are secure
- Lock dependency versions for production deployments

### Operational Security

- Implement proper logging for audit trails
- Consider limiting trade sizes and implementing circuit breakers for automated trading
- Test extensively before deploying to production
- Implement monitoring for abnormal behavior

### Code Security

- Validate all input data
- Do not modify the SDK core unless absolutely necessary
- If extending the SDK, follow secure coding practices
- Review the source code of any plugins or extensions before use

## Vulnerability Disclosure Policy

We follow these guidelines for disclosing vulnerabilities:

1. Security issues are addressed promptly
2. Fixes are thoroughly tested before release
3. Vulnerabilities are publicly disclosed after a fix is available
4. Users are encouraged to update as soon as possible
5. Credits are given to reporters who follow the responsible disclosure process

## Security Contacts

For security concerns, please contact:
- Email: security@projectx.com
- PGP Key: [Security PGP Key](https://projectx.com/pgp-key.txt)

## Compliance

When using this SDK for trading:
- Ensure compliance with all relevant financial regulations
- Be aware that this SDK handles financial data that may be subject to additional security requirements
- Consider implementing additional security measures for production trading systems

We appreciate your efforts in keeping the ProjectX Python SDK and its users secure!
