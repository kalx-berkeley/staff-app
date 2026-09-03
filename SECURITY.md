# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email the maintainers directly with details
3. Allow reasonable time for a fix before public disclosure

## Security Best Practices for Deployment

### ⚠️ CRITICAL: Before Production Deployment

This application contains template configuration files with placeholder values. **You MUST update these before deploying to production:**

#### 1. Apache Configuration (`apache/sites/auth.conf` and `apache/sites/staff.conf`)

**Required changes (must be identical in both files):**
- Replace `YOUR_GOOGLE_CLIENT_ID` with your Google OAuth2 client ID
- Replace `YOUR_GOOGLE_CLIENT_SECRET` with your Google OAuth2 client secret
- Replace `YOUR_OIDC_CRYPTO_PASSPHRASE` with a random passphrase: `openssl rand -base64 32`

#### 2. Environment Variables (`backend/.env`)

**Required configuration:**
```bash
# Update with your actual DJ studio network
DJ_STUDIO_NETWORK=192.168.1.0/24  # Example: adjust to your network

# For production, set to your actual domain(s)
CORS_ORIGINS=https://promotions.example.com

# If using Airtable integration
AIRTABLE_API_KEY=your_actual_api_key
AIRTABLE_BASE_ID=your_actual_base_id
```

#### 3. GitHub Secrets and Variables

Ensure all GitHub secrets and variables are properly configured per environment (staging and production):

**Variables:**
- `SITE_DOMAIN` - Your application domain
- `DJ_STUDIO_NETWORK` - DJ studio network CIDR
- `NETBIRD_HOSTNAME` - Netbird hostname (the bare peer hostname, not the FQDN — no domain suffix)

**Secrets:**
- `NETBIRD_SETUP_KEY` - Netbird setup key
- `SSH_PRIVATE_KEY` - SSH private key for deployment
- `AIRTABLE_API_KEY` - Airtable API key (optional)
- `AIRTABLE_BASE_ID` - Airtable base ID (optional)

**Note**: These are configured in GitHub environment settings (staging and production), so they have the same names but different values per environment.

### Security Features

This application implements several security best practices:

#### Authentication & Authorization
- **Two-path authentication**: every request is authenticated at the Apache layer by either a valid
  Google OIDC session or a source IP in the DJ studio network. Unauthenticated non-DJ requests are
  redirected to Google login; there is no anonymous access.
- **Role-Based Access Control (RBAC)**: Three distinct roles (promotions, staff, DJ) enforced by
  the backend.
- **Defense-in-depth authentication check**: the backend independently verifies that every `/api/`
  request carries either a Google identity (`X-Forwarded-User`) or a DJ studio network IP
  (`X-Forwarded-For`). If neither is present, the request is rejected with HTTP 400 and a CRITICAL
  log entry is emitted, indicating a server misconfiguration or Apache bypass.
- **Header-Based Identity**: Apache sets `X-Forwarded-User` from the verified OIDC email claim and
  strips any client-supplied `X-Forwarded-For` before setting the real client IP via mod_proxy.

#### Network Security
- **HTTPS Enforcement**: All HTTP traffic redirected to HTTPS
- **Security Headers**: HSTS, X-Frame-Options, X-Content-Type-Options, etc.
- **Service Isolation**: Backend binds to 127.0.0.1 only
- **Reverse Proxy**: Apache handles SSL termination, authentication, and request routing

#### Application Security
- **Input Validation**: Pydantic schemas with length constraints
- **SQL Injection Protection**: SQLAlchemy ORM with parameterized queries
- **CORS Configuration**: Configurable allowed origins
- **Error Handling**: Sanitized error messages without internal details

#### Infrastructure Security
- **User Separation**: Backend service runs as non-root `staff-app` user
- **Systemd Hardening**: NoNewPrivileges, PrivateTmp, ProtectSystem
- **Netbird Mesh Network**: Secure deployment without exposing SSH to internet
- **Automated Deployments**: GitHub Actions with secrets management

### DJ Studio Network Configuration

The `DJ_STUDIO_NETWORK` setting (set in both Apache and the backend `.env`) allows DJs to access
the system from specific IP addresses without a Google login. This is critical for live broadcast
workflow where the studio computer is shared and signing in with a personal account is impractical.

Both Apache and the backend check this CIDR independently:
- **Apache**: marks DJ studio network requests as authenticated (`IS_DJ_NETWORK` env var) and
  serves DJ-accessible paths without requiring an OIDC session.
- **Backend**: verifies the originating IP in the defense-in-depth check and grants DJ-specific
  endpoint access (`check_dj_access`) for requests from this range.

**Security considerations:**
- Use the most restrictive CIDR range possible
- Single IP: `192.168.1.100/32`
- Small subnet: `192.168.1.0/28` (16 addresses)
- Larger subnet: `192.168.1.0/24` (256 addresses)

**Avoid:**
- Using public IP ranges
- Using overly broad ranges (e.g., `0.0.0.0/0`)
- Exposing this to untrusted networks

### Regular Security Maintenance

#### SSL/TLS Certificates
- Certificates are automatically renewed by certbot
- Verify renewal: `sudo certbot renew --dry-run`
- Monitor expiration dates

#### Dependency Updates
- Regularly update Python dependencies: `pip install --upgrade -r requirements.txt`
- Update Node.js dependencies: `npm update`
- Monitor security advisories for dependencies

#### Log Monitoring
- Review Apache logs: `/var/log/apache2/promotions-*.log`
- Review backend logs: `journalctl --user -u promotions-app-backend`
- Look for suspicious patterns, failed authentication attempts, unusual traffic

#### Database Backups
- Implement automated daily backups
- Test backup restoration regularly
- Store backups securely off-site

#### Access Review
- Regularly review Google Workspace/Airtable user accounts
- Remove accounts for departed staff in Airtable (Airtable sync will revoke access)
- Audit role assignments

### Security Checklist

Before deploying to production, verify:

- [ ] Configured Google OAuth2 client ID and secret in Apache config
- [ ] Generated and set `OIDCCryptoPassphrase` in Apache config
- [ ] Registered correct redirect URI in Google Cloud Console
- [ ] Updated all domain placeholders to actual production domain
- [ ] Configured actual DJ studio network CIDR range
- [ ] Configured CORS_ORIGINS for production domain
- [ ] Set up all required GitHub secrets
- [ ] Verified SSL certificates are valid and auto-renewing
- [ ] Configured firewall to only allow ports 80, 443, and 22
- [ ] Enabled and tested automated database backups
- [ ] Reviewed and tested all authentication flows
- [ ] Verified backend service is running as non-root user
- [ ] Tested DJ network access from actual DJ studio
- [ ] Reviewed Apache security headers configuration
- [ ] Set up log monitoring and alerting
- [ ] Documented incident response procedures

### Known Security Considerations

#### DJ Network Bypass
The DJ studio network bypass is intentional to support live broadcast workflow. This means:
- Anyone on the DJ studio network can access DJ endpoints without authentication
- Ensure the DJ studio network is physically secure
- Consider additional network segmentation if needed
- Monitor DJ endpoint access in logs

#### SQLite Database
The application uses SQLite for simplicity. For production:
- SQLite is appropriate for this use case (low concurrent writes)
- Database file permissions are restricted to the `staff-app` user
- Regular backups are essential (no built-in replication)
- Consider PostgreSQL for higher-scale deployments

#### Airtable Integration
If using Airtable sync:
- API keys are stored in environment variables (acceptable practice)
- Sync process can add/remove users automatically
- Ensure Airtable access is properly secured
- Monitor sync logs for unexpected changes

### Incident Response

If you suspect a security incident:

1. **Immediate Actions:**
   - Review recent logs for suspicious activity
   - Check Apache auth logs for unauthorized access attempts
   - Verify database integrity
   - Review recent deployments

2. **Containment:**
   - Revoke Google OAuth credentials if compromised
   - Block suspicious IP addresses at firewall level
   - Consider taking the service offline if actively exploited

3. **Investigation:**
   - Preserve logs for analysis
   - Identify scope of compromise
   - Determine attack vector
   - Document timeline of events

4. **Recovery:**
   - Restore from clean backup if needed
   - Rotate Google OAuth credentials
   - Apply security patches
   - Verify system integrity before bringing back online

5. **Post-Incident:**
   - Document lessons learned
   - Update security procedures
   - Implement additional controls if needed
   - Notify affected users if required

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |

## Security Updates

Security updates will be released as needed. Monitor the repository for:
- Security advisories
- Dependency updates
- Configuration recommendations

## Additional Resources

- [Setup Guide](SETUP_GUIDE.md) - Complete setup, security, and deployment guide
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Apache Security Tips](https://httpd.apache.org/docs/2.4/misc/security_tips.html)
- [mod_auth_openidc](https://github.com/OpenIDC/mod_auth_openidc)
