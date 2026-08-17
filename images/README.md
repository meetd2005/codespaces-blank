# Notion screenshot map

All 75 screenshots were pulled from the original Notion page and saved as
`img00.png` .. `img74.png` in document order. Grouped by finding:

- **img00-img03** - Target intro / adPEAS domain recon
- **img04** - Forest trust to finance.corp (QUARANTINED)
- **img05-img14** - GPO signing, MachineAccountQuota, AD CS templates, privileged accounts, LAPS, BloodHound
- **img15-img17** - F-1 maintenance share, backup script, studentadmin runas
- **img18-img21** - F-2 Defender off, local-admin add, SafetyKatz STUDVM$ dump
- **img22-img24** - F-3 session hunting, PSRemoting, unconstrained delegation
- **img25-img32** - F-4 RBCD: asktgt, Set-DomainRBCD, S4U, MGMTSRV dump (techservice)
- **img33-img45** - F-5 ACL chain: techservice ACLs, Management group, ForceChangePassword puretech
- **img46-img51** - F-6 TECHSRV30 portproxy + SAM dump (securetech)
- **img52-img58** - F-7 srvusers recon, LSA SNMPTRAP causer, ADMINSRV86$
- **img59-img65** - F-8 AD CS ESC3: Certify FIDO agent, on-behalf-of techadmin, PKINIT DA TGT
- **img66-img74** - F-9 cross-forest: DCSync trust keys, inter-realm forge, TechOperations PEM, PKINIT, final flag
