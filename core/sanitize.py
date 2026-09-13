# core/sanitize.py
# Cômodo: pipeline determinístico blocklist → regex → Presidio.
# Por quê: sem LLM no filtro — rápido, auditável, previsível.

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any

from core import placeholders as ph

# --- Padrões estruturados (camada 2) ---

RE_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)
RE_EMAIL = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
)
# UPN / BloodHound principal (user@AD.LOCAL) — NÃO é e-mail SMTP
TLD_UPN_AD = (".local", ".lan", ".internal", ".corp", ".intranet")
RE_URL = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)
# Domínio simples (não captura versões tipo Apache 2.4.41)
# TLD mín. 3 chars — evita ticket.ki (sobra rbi de .kirbi)
RE_DOMAIN = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{3,}\b"
)
# FQDN com TLD de 2 letras (.br, .uk) — só mascara se for do cliente
RE_FQDN = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,}\b"
)
# CNPJ brasileiro (identifica a empresa no whois)
RE_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
# Telefone E.164 (whois Registrant Phone: +55.8199…)
RE_PHONE = re.compile(r"\+\d{1,3}[.\s-]?\d{6,14}\b")
# Whois ICANN: rua / CEP — rótulo da tool, valor é PII
RE_WHOIS_STREET = re.compile(r"(?im)^Registrant Street:\s*(.+?)\s*$")
RE_WHOIS_POSTAL = re.compile(r"(?im)^Registrant Postal Code:\s*(\S+)\s*$")
RE_WHOIS_CITY = re.compile(r"(?im)^Registrant City:\s*(.+?)\s*$")
# gitleaks: linha "Secret:      <valor>" (pode ter / de base64)
RE_GITLEAKS_SECRET = re.compile(r"(?im)^Secret:\s+(\S+)\s*$")
# GetADUsers.py / secretsdump.exe — NÃO são domínio
EXTENSOES_NAO_DOMINIO = (
    ".py",
    ".exe",
    ".dll",
    ".ps1",
    ".sh",
    ".bat",
    ".cmd",
    ".txt",
    ".md",
    ".json",
    ".xml",
    ".yml",
    ".yaml",
    ".log",
    ".rb",
    ".pl",
    ".js",
    ".ts",
    ".go",
    ".rs",
    ".zip",
    ".gz",
    ".pcap",
    ".kirbi",
    ".ccache",
)

# Impacket secretsdump: user:rid:lmhash:nthash:::
RE_SAM_HASH = re.compile(
    r"(?i)\b([A-Za-z0-9._$\\-]{1,64}):(\d+):"
    r"([0-9a-fA-F]{32}):([0-9a-fA-F]{32}):::"
)
# Hash / bootKey / dpapi (hex longo; evita 0x210 UAC)
# Inclui o prefixo 0x no span quando presente
RE_HEX_SECRET = re.compile(
    r"\b(0x[0-9a-fA-F]{32,}|[0-9a-fA-F]{32,})\b"
)
# Responder / ntlmrelayx: user::DOMAIN:challenge:ntproof:blob
RE_NTLMv2_HASH = re.compile(
    r"(?i)\b([A-Za-z0-9._$-]{1,64})::([A-Za-z0-9._$-]{0,64}):"
    r"([0-9a-fA-F]{16,}):([0-9a-fA-F]{32,}):([0-9a-fA-F]{8,})"
)
# DOMAIN/user:pass@host (GetADUsers.py estilo Impacket) — user SEM ponto (não é FQDN)
# (?<!/) evita hydra http-post-form /users/sign_in:body:fail → user/pass
RE_IMP_SLASH_USER_PASS = re.compile(
    r"(?i)(?<!/)\b([A-Za-z0-9_-]+)/([A-Za-z][A-Za-z0-9_-]{2,32}):"
    r"([^\s@:'\"]{4,128})"
)
# hydra: ^USER^ / ^PASS^ no módulo — não são credencial
RE_HYDRA_MARCADOR = re.compile(r"\^(?:USER|PASS)\^", re.IGNORECASE)
# mysql_sql: linhas "login   host" depois de mysql.user
RE_MYSQL_USER_ROW = re.compile(
    r"(?m)^[ \t]{2,}([A-Za-z][A-Za-z0-9._-]{1,32})[ \t]+"
    r"(%|localhost|[\w.%-]+)\s*$"
)
# MySQL grant host com curinga (10.8.4.%)
RE_IP_MYSQL_CURINGA = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){1,3}\.%)")
# Prefixos SPN — não são domínio NetBIOS de login
SPN_SERVICOS = {
    "mssqlsvc",
    "http",
    "cifs",
    "host",
    "ldap",
    "dns",
    "smtp",
    "imap",
    "pop",
    "ftp",
    "nfs",
    "termsrv",
    "wsman",
    "exchange",
    "gc",
}

# API keys / tokens — SEMPRE mascarar (lista FIXA; não depende do wizard)
# Cliente raramente cadastra isso; pode vazar em scan/config inesperado.
RE_APIKEY = re.compile(
    r"(?ix)"
    r"(?:"
    r"(?:api[_-]?key|apikey|access[_-]?token|secret[_-]?key)\s*[=:]\s*[\"']?"
    r"([A-Za-z0-9\-_.]{16,})"
    r"|(sk-[A-Za-z0-9]{20,})"
    r"|(sk_live_[A-Za-z0-9]{10,})"
    r"|(AKIA[0-9A-Z]{16})"
    r"|(glpat-[A-Za-z0-9_-]{10,})"
    r"|Bearer\s+([A-Za-z0-9\-._~+/]{20,}=*)"
    r"|(?:hooks\.slack\.com/services/)([A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+)"
    r")"
)

# Máscara / localhost de rota — não é IP de cliente
IPV4_NAO_MASCARAR = {
    "0.0.0.0",
    "255.0.0.0",
    "255.255.0.0",
    "255.255.255.0",
    "255.255.255.255",
    "127.0.0.1",
}

# Token curto demais → replace destrutivo (ex.: "IP" em PIPELINING, "sec" em seconds)
MIN_CHARS_MAPEAVEL = 4

# Contas built-in / genéricas — NÃO mascarar (raciocínio AD / Linux)
USERS_BUILTIN = {
    "administrator",
    "admin",
    "guest",
    "krbtgt",
    "root",
    "bin",
    "none",
    "daemon",
    "nobody",
    "nfsnobody",
    "www-data",
    "mysql",
    "postgres",
    "ubuntu",
    "debian",
    "sshd",
    "systemd",
    "user",
    "test",
    "default",
    "support",
    "info",
    "sales",
    "noreply",
    "no-reply",
    "mailer-daemon",
    "postmaster",
    "webmaster",
    "ftp",
    "anonymous",
}

# dotenv / .env: DB_PASSWORD=… (o \b de "password" falha em DB_PASSWORD)
RE_ENV_SECRET = re.compile(
    r"(?im)^([A-Z][A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|PSK|KEY|TOKEN))\s*=\s*(.+)$"
)
RE_ENV_USERNAME = re.compile(
    r"(?im)^[A-Z][A-Z0-9_]*(?:USERNAME|_USER)\s*=\s*"
    r"([A-Za-z][A-Za-z0-9._-]{2,64})\s*$"
)
# smtp-user-enum: "IP: login exists"
RE_SMTP_USER_EXISTS = re.compile(
    r"(?m)^[^\s:][\w.:]*:\s*([A-Za-z][A-Za-z0-9._-]{2,64})\s+exists\b"
)
RE_VRFY_USER = re.compile(
    r"(?i)\bVRFY\s+([A-Za-z][A-Za-z0-9._-]{2,64})\b"
)
SMTP_USER_NAO_CONTA = {
    "admin",
    "test",
    "teste",
    "guest",
    "root",
    "user",
    "enabled",
    "disabled",
    "exists",
    "users",
    "enum",
}
RE_ACCOUNT_USER = re.compile(
    r"(?i)\bAccount:\s*([A-Za-z][A-Za-z0-9._-]{2,32})\b"
)
RE_FOUND_USER_PAREN = re.compile(
    r"(?i)\bFound\s+user:\s*[^(\n]{0,80}\(\s*([A-Za-z][A-Za-z0-9._-]{2,32})\s*\)"
)
RE_USER_FIELD = re.compile(
    r"(?i)\b(?:Username|Login|sAMAccountName|SamAccountName)\s*[:=]\s*"
    r"['\"]?([A-Za-z][A-Za-z0-9._-]{2,32})\b"
)
# NetExec / CrackMapExec / BH logs: DOMAIN\user:password (aceita \\ escapado)
RE_NXC_DOM_USER_PASS = re.compile(
    r"(?i)(?:[A-Za-z0-9._-]+)\\{1,2}([A-Za-z][A-Za-z0-9._-]{2,32}):([^\s\"'{}\"<>]+)"
)
# Flags CLI: -p/-w/--ldappassword (SharpHound) / --password …
RE_CLI_PASSWORD = re.compile(
    r"(?i)(?:^|[\s])(?:-p|-w|--password|--passwd|--bind-password|"
    r"--ldappassword|--ldap-password)\s+"
    r"(?:'([^']+)'|\"([^\"]+)\"|(\S+))"
)
# Rubeus: /credpassword:Pass /password:Pass
RE_SLASH_FLAG_PASS = re.compile(
    r"(?i)/(?:credpassword|password|passwd|pass)\s*[:=]\s*"
    r"([^\s/\"']{4,128})"
)
# Label: Password: secret / pwd=secret
RE_PASS_LABEL = re.compile(
    r"(?i)(?:^|[\s_])(?:password|passwd|pwd|secret|psk)\s*[:=]\s*['\"]?([^\s'\"]+)"
)
# Comentário SMB: jsilva / TempPass!99  (exige espaços — não pega SPN MSSQLSvc/host)
RE_USER_SLASH_PASS = re.compile(
    r"(?i)\b([A-Za-z][A-Za-z0-9._-]{2,32})\s+/\s+([^\s\"'{}]{4,64})"
)
# Descrição LDAP/SMB/JSON: Admin local HOST - TempPass!99
# Não engole aspas/chaves JSON
RE_DASH_PASSWORD = re.compile(
    r"(?<=\S)\s+-\s+([^\s\"'{}]{4,64})(?=[\s\"'}]|$)"
)
# rpcclient / smbclient: -U 'DOMAIN/user%Password' ou user%Password
RE_PCT_PASSWORD = re.compile(
    r"%([^\s'\"%{}]{4,128})"
)
# rpcclient / samr / JSON BloodHound / whois Registro.br
RE_FULL_NAME_FIELD = re.compile(
    r"(?im)^(?:Full\s+Name|Display\s+Name|person|responsible|"
    r"Registrant\s+Name|Admin(?:istrative)?\s+Name|"
    r"Tech(?:nical)?\s+Name|Author)\s*:\s*(.+?)\s*$"
)
# WhatWeb: Meta-Author[Helena Voss - cargo]
RE_META_AUTHOR_NOME = re.compile(
    r"(?i)Meta-Author\[\s*"
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÀ][a-záéíóúâêôãõàç]+"
    r"(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÀ][a-záéíóúâêôãõàç]+){1,3})"
)
# openssl subject: ST = Pernambuco (estado no cert, não PERSON)
RE_CERT_ST = re.compile(
    r"\bST\s*=\s*([A-Za-z][A-Za-z ]{1,40}?)(?=,|\s*$)"
)
RE_NOME_LISTA_CARGO = re.compile(
    r"(?m)^[ \t]*"
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÀ][a-záéíóúâêôãõàç]+"
    r"(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÀ][a-záéíóúâêôãõàç]+){1,3})"
    r"[ \t]+-[ \t]+"
)
RE_JSON_DISPLAYNAME = re.compile(
    r'(?i)"(?:displayname|display_name|cn|name)"\s*:\s*"([^"]{3,80})"'
)
# GitLab / API REST: "username":"hvoss"
RE_JSON_USERNAME = re.compile(
    r'(?i)"username"\s*:\s*"([A-Za-z][A-Za-z0-9._-]{1,64})"'
)
# Nome antes de <email>
RE_NOME_ANTES_EMAIL = re.compile(
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÀ][a-záéíóúâêôãõàç]+"
    r"(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÀ][a-záéíóúâêôãõàç]+)+)"
    r"\s*<"
)
# "Jose Silva Admin local HOST - pass"
RE_NOME_ADMIN_LOCAL = re.compile(
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÀ][a-záéíóúâêôãõàç]+"
    r"(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÀ][a-záéíóúâêôãõàç]+)+)"
    r"\s+Admin\s+local\b"
)
# Rubeus / LDAP: SamAccountName         : sqlsvc
RE_SAMACCOUNT_FIELD = re.compile(
    r"(?i)SamAccountName\s*:\s*([A-Za-z][A-Za-z0-9._$-]{1,64})"
)
# NetExec SAMR: - cmendes (Carla Mendes)  (pode vir após colunas SMB)
RE_NXC_DASH_USER = re.compile(
    r"(?i)(?:^|[\s])-\s*([A-Za-z][A-Za-z0-9._-]{2,32})\s*\("
)
# LDAP dump de users: exige e-mail ou <email> na linha (evita header Share / nomes de share)
RE_NXC_LDAP_USER = re.compile(
    r"(?m)^(?:LDAP|SMB)\s+\S+\s+\d+\s+\S+\s+"
    r"([A-Za-z][A-Za-z0-9._-]{2,32})\s{2,}.+@"
)
# Nome completo entre parênteses: (Marina Braga)
RE_NOME_PAREN = re.compile(
    r"\("
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÀ][a-záéíóúâêôãõàç]+"
    r"(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÀ][a-záéíóúâêôãõàç]+)+)"
    r"\)"
)

# Palavras de output NetExec/SMB que NÃO são login (header / share / permissão)
# Inclui shares comuns PT/EN — Presidio/USER não podem virar PERSON
USERS_NAO_LOGIN = {
    "share",
    "shares",
    "permissions",
    "permission",
    "remark",
    "read",
    "write",
    "only",
    "disk",
    "ipc",
    "admin",
    "type",
    "comment",
    "enumerated",
    "domain",
    "users",
    "via",
    "samr",
    "getting",
    "base",
    "info",
    "dumping",
    "computers",
    "description",
    "contact",
    "server",
    "logon",
    "service",
    "backup",
    "vendor",
    "vpn",
    "access",
    "file",
    "departamentos",
    "departamento",
    "financeiro",
    "public",
    "publico",
    "pública",
    "publica",
    "private",
    "privado",
    "homes",
    "home",
    "print$",
    "users$",
    "prontuarios",
    "prontuarios_2024",
    "ti_interno",
    "scans_rh",
    "backup_contabil",
    "captive",
    "smbmap",
    "authenticated",
    "manager",
    "workstations",
    "workstation",
    "segment",
    "edge",
    "sign_in",
    "sign_up",
    # ldapsearch / LDIF — Presidio confunde com PERSON/ORG
    "success",
    "binding",
    "bound",
    "ldapsearch",
    "ldif",
    "ldapv3",
    "subtree",
    "filter",
    "requesting",
    "extended",
    "samaccountname",
    "userprincipalname",
    "displayname",
    "memberof",
    "objectclass",
    "dnshostname",
    "operatingsystem",
    "telephonenumber",
    "department",
    "title",
    # rpcclient labels (Presidio → PERSON destrói a linha)
    "home",
    "drive",
    "profile",
    "path",
    "home drive",
    "profile path",
    "primary group",
    "full name",
    "user name",
    "rpcclient",
    "querydominfo",
    "enumdomusers",
    "netshareenum",
    "getdcname",
    "lsaquery",
    "queryuser",
    "netname",
    "remark",
    "total users",
    "domain sid",
    "remote admin",
    "default share",
    "remote ipc",
    "logon server share",
    "public share",
    "home folders",
    # Impacket / secretsdump / Kerberos
    "impacket",
    "getadusers",
    "getuserspns",
    "lookupsid",
    "secretsdump",
    "querying",
    "lastlogon",
    "passwordlastset",
    "memberof",
    "serviceprincipalname",
    "sidtypeuser",
    "sidtypegroup",
    "domain admins",
    "domain users",
    "bootkey",
    "dumping",
    "brute forcing",
    "clearing",
    "related",
    "contacts",
    "people",
    "uid",
    "rid",
    "lmhash",
    "nthash",
    "mssqlsvc",
    "http",
    "fortra",
    "contributors",
    "copyright",
    "never",
    "uac",
    "sam",
    "lsa",
    "dpapi_machinekey",
    "dpapi",
    "target system",
    "domain credentials",
    "local sam hashes",
    "iis_usrs",
    "mssqlserver",
    "sc_mssqlserver",
    "_sc_mssqlserver",
    # BloodHound / SharpHound
    "sharphound",
    "bloodhound",
    "localadmin",
    "localadmins",
    "trusts",
    "container",
    "objectprops",
    "domaincontroller",
    "hassession",
    "collection",
    "methods",
    "information",
    "resolved",
    "initializing",
    "producer",
    "estimating",
    "enumeration",
    "graphing",
    "community",
    "edition",
    "loop",
    "flags",
    "session",
    "acl",
    "rdp",
    "spn",
    "objectid",
    "memberid",
    "membertype",
    "membername",
    "properties",
    "distinguishedname",
    "samaccountname",
    "displayname",
    "domainsid",
    "admincount",
    "pwdlastset",
    "lastlogon",
    "hasspn",
    "serviceprincipalnames",
    "operatingsystem",
    "enabled",
    "admincount",
    # Responder / ntlmrelayx
    "responder",
    "ntlmrelayx",
    "poisoners",
    "poisoned",
    "poisoning",
    "llmnr",
    "nbt-ns",
    "nbtns",
    "mdns",
    "ntlmv2",
    "ntlmv2-ssp",
    "cleartext",
    "skipping",
    "analyzing",
    "workgroup",
    "protocol",
    "relay",
    "smbd-relay",
    "succeed",
    "enumerating",
    "privileged",
    "listening",
    "servers",
    "smb2support",
    # kerbrute / Rubeus
    "kerbrute",
    "rubeus",
    "kerberoasting",
    "kerberoast",
    "asktgt",
    "userenum",
    "passwordspray",
    "samaccountname",
    "distinguishedname",
    "serviceprincipalname",
    "base64",
    "kirbi",
    "ticket",
    "outfile",
    "creduser",
    "credpassword",
    "nowrap",
    "ptt",
    "ropnop",
    "kdc",
    "spraying",
    "valid",
    "username",
    "login",
    "action",
    "successful",
    "dump",
    "luid",
    "service accounts",
    "web app",
    "sql service",
}

# Status / ruído após senha — não tratar como password
PASS_NAO_MASCARAR = {
    "status_logon_failure",
    "status_access_denied",
    "status_password_expired",
    "status_account_locked_out",
    "status_wrong_password",
    "(null)",
    "null",
    "guest",
}

# Tecnologias / CVE / protocolos — NÃO mascarar (análise técnica intacta)
# Inclui falsos positivos do nmap de validação (Microsoft, Ubuntu, Dovecot, …)
ALLOW_TECNICO = re.compile(
    r"\b(?:"
    r"CVE-\d{4}-\d+"
    r"|Apache|nginx|OpenSSH|OpenSSL|MySQL|PostgreSQL|MongoDB"
    r"|WordPress|Drupal|Joomla|Tomcat|IIS|SMB|FTP|SSH|HTTP|HTTPS"
    r"|DNS|SNMP|RDP|LDAP|Kerberos|Nmap|Metasploit|SQLMap"
    r"|Python|PHP|Java|Node\.?js|React|Docker|Kubernetes"
    # Vendor / OS / serviços comuns em banner de scan (não são cliente)
    r"|Microsoft|Windows|Ubuntu|Linux|Debian|CentOS|Red\s*Hat|Fedora"
    r"|Samba|Dovecot|Postfix|Roundcube|Bind|ISC"
    r"|POP3|IMAP|SMTP|NetBIOS|msrpc|RPC"
    r"|Active\s+Directory|Simple\s+DNS\s+Plus"
    r"|PORT|STATE|SERVICE|VERSION"
    # Jargão nmap / banner que Presidio confunde com PERSON
    r"|tcp\s+ports|udp\s+ports|ports"
    r"|Jump\s+Gateway|Gateway"
    r"|Domain\s+Controller"
    r"|rootdse|ldap-rootdse|nbstat|kpasswd5"
    r"|Host\s+is\s+up|Not\s+shown|Nmap\s+done"
    r"|PIPELINING|SIZE|VRFY|ETRN|STARTTLS|ENHANCEDSTATUSCODES|QUIT"
    # enum4linux / AD enum — rótulos e contas built-in (não são cliente)
    r"|Desc|Description|Groups|Group"
    r"|Default|Logon|NETLOGON|SYSVOL|ADMIN\$|IPC\$|C\$"
    r"|krbtgt|Administrator|Guest|Domain\s+Admins|Domain\s+Users"
    r"|Remote\s+Desktop\s+Users|Administrators|Users|Guests"
    r"|Workgroup|Domain\s+Name|Domain\s+Sid|RID|RID\s+Range"
    r"|enum4linux|theHarvester|WhatWeb|Gobuster|rpcclient|LinkedIn|Google|Bing|DuckDuckGo"
    r"|crt\.sh|Registro\.br|Nic\.br|cert\.br|whois\.registro\.br"
    r"|Edge-?Security|Christian\s+Martorella"
    r"|Sun|Mon|Tue|Wed|Thu|Fri|Sat"
    r"|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    r"|Security\s+Analyst|Sysadmin|Helpdesk|Business\s+Partner|External"
    r"|Known\s+Usernames|Usernames|Username|Password"
    r"|Target|Targets|Information"
    r"|STATUS_LOGON_FAILURE|SMBv1|SAMR|Enumerated|Permissions|Remark|signing"
    r"|SOC\s+lead|Backup\s+service\s+account|HR\s+business\s+partner"
    # smbmap / share table (não são PERSON)
    r"|smbmap|Disk|Comment|Authenticated|Manager|Contact|Workstations?"
    r"|Departamentos?|Financeiro|Publico|Público|Prontuarios?(?:_\d+)?"
    r"|TI_Interno|Scans_RH|Backup_Contabil|Public\s+edge|Lab\s+segment"
    r"|Guest\s+WiFi|Backup\s+DC|READ(?:\s*,\s*WRITE|\s+ONLY)?|NO\s+ACCESS"
    r"|ONLY|captive|homes"
    # ldapsearch / LDIF (falso positivo Helios)
    r"|ldapsearch|LDIF|LDAPv3|Success|Binding|Bound"
    r"|sAMAccountName|userPrincipalName|displayName|memberOf"
    r"|objectClass|dNSHostName|operatingSystem|telephoneNumber"
    r"|department|title|subtree|filter|requesting|extended"
    # rpcclient (falso positivo Helios)
    r"|rpcclient|querydominfo|enumdomusers|netshareenum|getdcname|lsaquery"
    r"|queryuser|netname|Home\s+Drive|Profile\s+Path|Primary\s+Group"
    r"|Full\s+Name|User\s+Name|Total\s+Users|Domain\s+SID|Domain\s+Name"
    r"|Remote\s+Admin|Default\s+share|Remote\s+IPC|Logon\s+server\s+share"
    r"|Public\s+share|home\s+folders|Server|Comment"
    # Impacket
    r"|Impacket|GetADUsers|GetUserSPNs|lookupsid|secretsdump|Fortra"
    r"|Querying|LastLogon|PasswordLastSet|MemberOf|ServicePrincipalName"
    r"|SidTypeUser|SidTypeGroup|Domain\s+Admins|Domain\s+Users"
    r"|bootKey|Dumping|Brute\s+forcing|Clearing|Related|Contacts|People"
    r"|uid|rid|lmhash|nthash|MSSQLSvc|IIS_USRS"
    r"|SAM|LSA|dpapi_machinekey|dpapi|UAC|<never>|Copyright|contributors"
    r"|Target\s+system|Domain\s+Credentials|local\s+SAM\s+hashes"
    r"|_SC_[A-Za-z0-9_]+|MSSQLSERVER|SERVICE_NAME"
    # BloodHound / SharpHound
    r"|SharpHound|BloodHound|LocalAdmin|LocalAdmins|Trusts|Container"
    r"|ObjectProps|DomainController|HasSession|Collection\s+Methods"
    r"|INFORMATION|Resolved|Initializing|Producer|Estimating|Enumeration"
    r"|Graphing|Community\s+Edition|Loop|Flags|Session|ACL|RDP|SPN"
    r"|ObjectId|MemberId|MemberType|MemberName|Properties"
    r"|distinguishedname|samaccountname|displayname|domainsid"
    r"|admincount|pwdlastset|lastlogon|hasspn|serviceprincipalnames"
    r"|operatingsystem|Happy\s+Graphing|Beginning\s+LDAP\s+search"
    # Responder / ntlmrelayx
    r"|Responder|ntlmrelayx|Poisoners|Poisoned|Poisoning|LLMNR|NBT-NS|MDNS"
    r"|NTLMv2(?:-SSP)?|Cleartext|Skipping|Analyzing|WORKGROUP"
    r"|Protocol\s+Client|relay\s+mode|SMBD-Relay|SUCCEED|Enumerating"
    r"|privileged|Listening|Servers\s+started|smb2support"
    # kerbrute / Rubeus
    r"|kerbrute|Rubeus|Kerberoasting|Kerberoast|asktgt|userenum|passwordspray"
    r"|hydra|Hydra|Helm|http-post-form|https-post-form|mysql_sql"
    r"|SamAccountName|DistinguishedName|ServicePrincipalName|base64|kirbi"
    r"|VALID\s+USERNAME|VALID\s+LOGIN|Done\s+spraying|Ask\s+TGT|Dump\s+Ticket"
    r"|Target\s+LUID|Target\s+Domain|Domain\s+Controller|Using\s+credentials"
    r"|kerberoastable|outfile|creduser|credpassword|nowrap|Service\s+Accounts"
    r"|SQL\s+Service|Web\s+App|KDC|ropnop"
    # nmap ssl/smtp + WhatWeb (rótulos, não cliente)
    r"|Colaborador|Issuer|Public\s+Key|Meta-Author"
    r"|UncommonHeaders|HTTPServer|PasswordField|HTML5"
    r"|Strict-Transport-Security|X-Powered-By|X-Internal-Host"
    r"|OpenVPN|GlobalProtect|Palo\s+Alto|Let's\s+Encrypt"
    r"|DOCTYPE|nc\s+-nv|smtp-user-enum"
    r"|gitleaks|IONOS|IANA|Expiry(?:\s+Date)?"
    r"|Jump(?:\s+host)?"
    r"|[KMGT]i?B(?:/s)?"
    r"|Control\s+Plane|Edge\s+Control"
    r"|[A-Z]{2,12}SESSID"
    r")\b",
    re.IGNORECASE,
)

# ------------------------------------------------------------------
# TABELA — o que NÃO filtrar (placeholders / padrões seguros)
# Auditoria: se aparecer no preview sem ser cliente, entra aqui.
# ------------------------------------------------------------------
# • Versões de software (2.4.41, 8.2.0)
# • Tempos / latency (0.000012s)
# • Arte de terminal / box-drawing (┌──, ㉿)
# • CVEs e nomes de vulnerabilidades conhecidas
# • Protocolos / stacks (SSH, HTTP, Apache, Nmap, …)
# • Domínios públicos de ferramentas (lista abaixo)
# ------------------------------------------------------------------
DOMINIOS_PUBLICOS = {
    "nmap.org",
    "github.com",
    "githubusercontent.com",
    "raw.githubusercontent.com",
    "gitlab.com",
    "bitbucket.org",
    "google.com",
    "googleapis.com",
    "microsoft.com",
    "windowsupdate.com",
    "ubuntu.com",
    "debian.org",
    "kali.org",
    "offsec.com",
    "tryhackme.com",
    "hackthebox.com",
    "hackthebox.eu",
    "wikipedia.org",
    "w3.org",
    "ietf.org",
    "iana.org",
    "localhost",
    "portcullis.co.uk",
    "labs.portcullis.co.uk",
    "linkedin.com",
    "google.com",
    "registro.br",
    "nic.br",
    "cert.br",
    "edge-security.com",
    "bing.com",
    "duckduckgo.com",
    "ionos.com",
    "cloudflare.com",
    "icann.org",
    "mailgun.org",
    "amazonaws.com",
}

# Tempo / ruído de terminal (ex.: 0.000012s, box-drawing)
RE_LIXO = re.compile(
    r"(?:"
    r"^[\d.]+\s*s$"  # 0.000012s
    r"|^[\d.]+$"  # só número/versão
    r"|^latency$"
    r"|^rtt$"
    r"|^[^\w]+$"  # só símbolos (┌──, etc.)
    r"|^[\W_]{1,8}$"
    r")",
    re.IGNORECASE,
)

# Threshold: cobre cliente sem engolir ruído óbvio
PRESIDIO_SCORE = 0.45

MAPA_PRESIDIO = {
    "PERSON": "PERSON",
    "ORGANIZATION": "ORG",
    "NRP": "ORG",
    "EMAIL_ADDRESS": "EMAIL",
    "IP_ADDRESS": "IP",
    "URL": "DOMAIN",
    "DOMAIN_NAME": "DOMAIN",
}


@dataclass
class Achado:
    real_value: str
    entity_type: str
    start: int
    end: int
    camada: str  # blocklist | regex | presidio


@dataclass
class ResultadoSanitize:
    texto_original: str
    texto_sanitizado: str
    resumo: list[dict[str, Any]] = field(default_factory=list)
    # Para COMMIT no ACEPT / ROLLBACK no CANCEL
    novos_mapeamentos: list[dict[str, Any]] = field(default_factory=list)
    increments: list[tuple[int, int]] = field(default_factory=list)
    teve_sensivel: bool = False


class Sanitizer:
    """Motor de sanitização por engagement (reutiliza Analyzer)."""

    def __init__(self) -> None:
        self._analyzer = None
        self._presidio_ok = False
        self._carregar_presidio()

    def _carregar_presidio(self) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            provider = NlpEngineProvider(
                conf_file=None,
            )
            # Configuração leve en_core_web_sm
            nlp_configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            }
            try:
                nlp_engine = NlpEngineProvider(
                    nlp_configuration=nlp_configuration
                ).create_engine()
                self._analyzer = AnalyzerEngine(
                    nlp_engine=nlp_engine, supported_languages=["en"]
                )
            except TypeError:
                self._analyzer = AnalyzerEngine()
            self._presidio_ok = True
        except Exception:
            self._analyzer = None
            self._presidio_ok = False

    # --- Camada 1: blocklist tipada ---

    def _achados_blocklist(
        self, texto: str, eng: dict[str, Any]
    ) -> list[Achado]:
        itens: list[tuple[str, str]] = []
        for ip in eng.get("ip_ranges") or []:
            itens.append((ip, "IP"))
        for d in eng.get("domains") or []:
            # host e domain na mesma lista operacional
            tipo = "HOST" if "." in d and not self._parece_dominio_puro(d) else "DOMAIN"
            if self._eh_ip(d):
                tipo = "IP"
            elif "." in d:
                tipo = "DOMAIN"
            else:
                tipo = "HOST"
            itens.append((d, tipo))
        for n in eng.get("known_contacts") or []:
            # email → EMAIL; empresa/marca → ORG; login sem espaço → USER; nome → PERSON
            if "@" in n:
                itens.append((n, "EMAIL"))
            elif self._parece_marca_ou_empresa(n):
                itens.append((n, "ORG"))
            elif self._parece_login_simples(n):
                itens.append((n, "USER"))
            else:
                itens.append((n, "PERSON"))
        for v in eng.get("client_name_variants") or []:
            itens.append((v, "ORG"))
        if eng.get("client_name"):
            itens.append((eng["client_name"], "ORG"))

        achados: list[Achado] = []
        # Mais longos primeiro evita overlap parcial
        itens_unicos = {(v, t) for v, t in itens if v}
        ordenados = sorted(itens_unicos, key=lambda x: len(x[0]), reverse=True)
        for valor, tipo in ordenados:
            if self._eh_jargao_share_ou_rotulo(valor):
                continue
            if not self._token_mapeavel(valor, tipo):
                continue
            for m in re.finditer(re.escape(valor), texto, flags=re.IGNORECASE):
                if tipo in {"ORG", "PERSON"} and self._eh_prefixo_de_fqdn(
                    texto, m.end()
                ):
                    continue
                achados.append(
                    Achado(
                        real_value=texto[m.start() : m.end()],
                        entity_type=tipo,
                        start=m.start(),
                        end=m.end(),
                        camada="blocklist",
                    )
                )
        return achados

    def _achados_mapa_existente(
        self,
        texto: str,
        repo: Any,
        engagement_id: int,
        eng: dict[str, Any],
    ) -> list[Achado]:
        """
        Replay do mapa deste eng: mesmo valor → mesmo placeholder.
        Não é blocklist do wizard; é consistência entre PAST INPUTs.
        """
        try:
            rows = repo.listar_mapeamentos(engagement_id)
        except Exception:
            return []
        itens: list[tuple[str, str]] = []
        for row in rows:
            valor = (row.get("real_value") or "").strip()
            tipo = (row.get("entity_type") or "ID").upper()
            if not valor:
                continue
            # Mapa sujo: *.host / .host não reentrar (cola *TARGET_)
            if valor.startswith(("*.", "*")) or (
                valor.startswith(".") and "." in valor[1:]
            ):
                continue
            itens.append((valor, tipo))
            if valor.lower().startswith("base64:"):
                resto = valor.split(":", 1)[1].strip()
                if resto:
                    itens.append((resto, tipo))
        achados: list[Achado] = []
        ordenados = sorted(itens, key=lambda x: len(x[0]), reverse=True)
        for valor, tipo in ordenados:
            if valor.upper().startswith(
                ("TARGET_", "PERSON_", "CLIENT_", "EMAIL_")
            ):
                continue
            if self._eh_jargao_share_ou_rotulo(valor):
                continue
            if not self._token_mapeavel(valor, tipo):
                continue
            if tipo == "IP" and valor in IPV4_NAO_MASCARAR:
                continue
            if ALLOW_TECNICO.search(valor) or self._na_allow_lista(valor, eng):
                continue
            flags = (
                re.IGNORECASE
                if tipo in {"DOMAIN", "HOST", "EMAIL", "ORG", "PERSON", "USER"}
                else 0
            )
            for m in re.finditer(re.escape(valor), texto, flags=flags):
                if tipo in {"ORG", "PERSON"} and self._eh_prefixo_de_fqdn(
                    texto, m.end()
                ):
                    continue
                achados.append(
                    Achado(
                        real_value=texto[m.start() : m.end()],
                        entity_type=tipo,
                        start=m.start(),
                        end=m.end(),
                        camada="blocklist",
                    )
                )
        return achados

    @staticmethod
    def _parece_login_simples(valor: str) -> bool:
        """Login AD típico (cmendes) — sem espaço; não é nome completo."""
        v = (valor or "").strip()
        return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]{2,32}", v))

    @staticmethod
    def _parece_marca_ou_empresa(valor: str) -> bool:
        """Razão social / marca (MareClara, S.A., Ltda) — não é login nem pessoa."""
        v = (valor or "").strip()
        if not v:
            return False
        if re.search(
            r"(?i)\b(?:S\.?\s*A\.?|Ltda\.?|Ltd\.?|Inc\.?|LLC|GmbH|Corp\.?)\b",
            v,
        ):
            return True
        # PascalCase de marca (MareClara) — não é sAMAccountName
        if " " not in v and re.search(r"[a-z][A-Z]", v):
            return True
        return False

    @staticmethod
    def _eh_rotulo_http_ou_scan(valor: str) -> bool:
        """Rótulo de nmap/WhatWeb/HTTP — não é nome de cliente."""
        v = (valor or "").strip()
        if not v:
            return False
        if re.fullmatch(
            r"(?i)WhatWeb|Meta-Author|UncommonHeaders|HTTPServer|"
            r"PasswordField|Issuer|Public\s+Key|Colaborador|"
            r"VRFY|ETRN|STARTTLS|"
            r"Strict-Transport-Security|X-Powered-By|X-Internal-Host|"
            r"X-[A-Za-z0-9-]+|"
            r"Expiry(?:\s+Date)?|Jump(?:\s+host)?|"
            r"[KMGT]i?B(?:/s)?|"
            r"Organization|Registry|Registrar|IANA|IONOS|"
            r"gitleaks|Finding|RuleID|Author|"
            r"Edge\s+Control(?:\s+Plane)?|Control\s+Plane|"
            r"[A-Z]{2,12}SESSID",
            v,
        ):
            return True
        # WhatWeb: Header[X-Internal-Host …
        if re.match(r"(?i)header\s*\[", v):
            return True
        if re.match(r"(?i)gobuster\b", v):
            return True
        if re.fullmatch(r"(?i)DOCTYPE", v):
            return True
        return False

    @staticmethod
    def _normalizar_span_dominio(valor: str) -> str:
        """Tira *. e ponto à esquerda — senão *.nyxlynx.io vira *TARGET_DOMAIN."""
        v = (valor or "").strip()
        v = re.sub(r"^\*\.", "", v)
        return v.lstrip(".")

    @staticmethod
    def _eh_prefixo_de_fqdn(texto: str, fim: int) -> bool:
        """True se o match é só o label (NyxLynx) e o texto segue como host (.internal)."""
        return 0 <= fim < len(texto) and texto[fim] == "."

    def _dominio_do_cliente(
        self, valor: str, eng: dict[str, Any] | None
    ) -> bool:
        """Host/domínio do scope (ou TLD interno). Infra pública (registro.br) fica de fora."""
        v = (valor or "").lower().strip().strip(".")
        if not v:
            return False
        if v.endswith((".local", ".lan", ".internal", ".corp", ".intranet")):
            return True
        conhecidos: list[str] = []
        for d in (eng or {}).get("domains") or []:
            dd = (d or "").lower().strip().strip(".")
            if dd and not self._eh_ip(dd):
                conhecidos.append(dd)
        for d in conhecidos:
            if v == d or v.endswith("." + d):
                return True
        return False

    @staticmethod
    def _eh_jargao_share_ou_rotulo(valor: str) -> bool:
        """Share / permissão / rótulo de tool — nunca mascarar como PERSON/USER."""
        baixo = (valor or "").casefold().strip()
        if not baixo:
            return False
        if baixo in USERS_NAO_LOGIN:
            return True
        # Tokens tipo Prontuarios_2024 / TI_Interno
        compacto = baixo.replace("-", "_")
        if compacto in USERS_NAO_LOGIN:
            return True
        return False

    @staticmethod
    def _eh_ip(valor: str) -> bool:
        try:
            ipaddress.ip_address(valor)
            return True
        except ValueError:
            return False

    @staticmethod
    def _parece_dominio_puro(valor: str) -> bool:
        return bool(RE_DOMAIN.fullmatch(valor))

    @staticmethod
    def _dominio_publico(valor: str) -> bool:
        v = valor.lower().strip(".")
        if v in DOMINIOS_PUBLICOS:
            return True
        return any(v == d or v.endswith("." + d) for d in DOMINIOS_PUBLICOS)

    @staticmethod
    def _eh_lixo(valor: str) -> bool:
        v = valor.strip()
        if len(v) < 2:
            return True
        # IP válido nunca é lixo
        try:
            ipaddress.ip_address(v)
            return False
        except ValueError:
            pass
        # SID AD (S-1-5-21-…) — sensível, não é ruído
        if re.fullmatch(r"S-1-\d+(?:-\d+)+", v):
            return False
        # Hash / challenge NTLM / bootKey hex — sensível
        if re.fullmatch(r"(?i)(?:0x)?[0-9a-f]{16,}", v):
            return False
        # CEP BR (00000-000) — PII de whois, não é ruído
        if re.fullmatch(r"\d{5}-\d{3}", v):
            return False
        if RE_LIXO.match(v):
            return True
        # Box-drawing / arte de terminal
        if any(ord(c) >= 0x2500 and ord(c) <= 0x257F for c in v):
            return True
        # Prompt kali / fragmentos com símbolos especiais
        if "㉿" in v or "[~]" in v or v.startswith("─┤") or ")-[" in v:
            return True
        # Pouca letra → ruído (ex.: ㉿kali)-[~)
        letras = sum(1 for c in v if c.isalpha())
        if letras < 2 and not ("@" in v or "." in v):
            return True
        return False

    # --- Camada 2: regex ---

    @staticmethod
    def _token_mapeavel(valor: str, entity_type: str) -> bool:
        """
        Bloqueia tokens curtos que destroem texto no replace global
        (ex.: "IP" → quebra PIPELINING / TARGET_IP_1; "sec" → seconds).
        IP completo e email passam pela regra própria.
        """
        tipo = entity_type.upper()
        if tipo == "IP":
            return True
        if tipo == "EMAIL":
            return "@" in valor and len(valor) >= MIN_CHARS_MAPEAVEL
        if tipo == "APIKEY":
            return len(valor) >= 12
        if tipo == "USER":
            return 3 <= len(valor) <= 32
        if tipo == "PASSWORD":
            return 4 <= len(valor) <= 128
        if tipo == "ID":
            return len(valor) >= 11
        return len(valor) >= MIN_CHARS_MAPEAVEL

    def _eh_username_cliente(self, user: str, eng: dict[str, Any]) -> bool:
        """True se parece login de cliente (não built-in / não allow)."""
        u = (user or "").strip()
        if not u or not self._token_mapeavel(u, "USER"):
            return False
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]*", u):
            return False
        if RE_HYDRA_MARCADOR.fullmatch(u):
            return False
        baixo = u.casefold()
        if baixo in USERS_BUILTIN or self._eh_jargao_share_ou_rotulo(u):
            return False
        if self._na_allow_lista(u, eng):
            return False
        if ALLOW_TECNICO.search(u):
            return False
        if self._eh_ip(u) or self._dominio_publico(u):
            return False
        if "@" in u:
            return False
        return True

    @staticmethod
    def _parece_senha(valor: str) -> bool:
        """Heurística: evita Presidio tratar senha como PERSON/ORG."""
        v = (valor or "").strip()
        if not v or " " in v:
            return False
        if RE_HYDRA_MARCADOR.fullmatch(v):
            return False
        if v.casefold() in PASS_NAO_MASCARAR:
            return False
        if re.search(r"[!@$%#*&]", v):
            return True
        if re.search(r"(?i)(?:pass|pwd|welcome|summer|secret|p@ss|temp)", v):
            return True
        # Mistura letra+dígito curta (Passw0rd, Welcome1)
        if re.search(r"[A-Za-z]", v) and re.search(r"\d", v) and len(v) <= 24:
            return True
        return False

    def _eh_password_cliente(self, senha: str) -> bool:
        s = (senha or "").strip().strip("'\"")
        if not s or not self._token_mapeavel(s, "PASSWORD"):
            return False
        if s.casefold() in PASS_NAO_MASCARAR:
            return False
        if RE_HYDRA_MARCADOR.fullmatch(s):
            return False
        if s.upper().startswith("STATUS_"):
            return False
        if self._eh_ip(s):
            return False
        # Path / URL / flag — não é senha.
        # AWS secret é base64 com / no meio: NÃO recusar só por ter barra.
        if s.startswith(("-", "/", "./", "../")) or "\\" in s or "://" in s:
            return False
        if re.match(r"^(/[A-Za-z0-9._-]+){2,}$", s):
            return False
        # secretsdump: rid:lmhash:nthash::: — não é senha única
        if re.match(r"(?i)^\d+:[0-9a-f]{32}:[0-9a-f]{32}", s):
            return False
        # rótulos de formato (uid:rid:lmhash:nthash)
        if re.match(r"(?i)^(rid|lmhash|nthash)\b", s):
            return False
        if s.casefold() in {"rid:lmhash:nthash)", "rid:lmhash:nthash"}:
            return False
        return True

    @staticmethod
    def _eh_hash_secretsdump_tail(senha: str) -> bool:
        """True se o 'password' do DOMAIN\\user:… é na verdade rid:lm:nt."""
        return bool(
            re.match(r"(?i)^\d+:[0-9a-f]{32}:[0-9a-f]{32}", (senha or "").strip())
        )

    def _achados_usernames(
        self, texto: str, eng: dict[str, Any]
    ) -> list[Achado]:
        """
        Logins em contexto de conta (enum4linux + NetExec/CME).
        Propaga o mesmo USER em todas as ocorrências com fronteira de palavra.
        """
        candidatos: list[str] = []
        vistos: set[str] = set()

        def _add(bruto: str) -> None:
            chave = bruto.casefold()
            if chave in vistos:
                return
            if not self._eh_username_cliente(bruto, eng):
                return
            vistos.add(chave)
            candidatos.append(bruto)

        for rx in (
            RE_ACCOUNT_USER,
            RE_FOUND_USER_PAREN,
            RE_USER_FIELD,
            RE_NXC_DASH_USER,
            RE_NXC_LDAP_USER,
            RE_SAMACCOUNT_FIELD,
            RE_JSON_USERNAME,
        ):
            for m in rx.finditer(texto):
                _add(m.group(1))

        for m in RE_NXC_DOM_USER_PASS.finditer(texto):
            _add(m.group(1))

        for m in RE_IMP_SLASH_USER_PASS.finditer(texto):
            if m.group(1).casefold() in SPN_SERVICOS:
                continue
            # hydra/form HTTP — não é DOMAIN/user:pass do Impacket
            if re.search(r"[=&\[]", m.group(3) or ""):
                continue
            _add(m.group(2))

        for m in RE_USER_SLASH_PASS.finditer(texto):
            # lado esquerdo do "user / senha"
            if self._parece_senha(m.group(2)):
                _add(m.group(1))

        # secretsdump / sam: user:rid:lmhash:nthash:::
        for m in RE_SAM_HASH.finditer(texto):
            user = m.group(1)
            # ignora DOMAIN\user já coberto; pega só o user final
            if "\\" in user:
                user = user.rsplit("\\", 1)[-1]
            if user.endswith("$"):
                # machine account FILE01$ — host-like; trata como USER de máquina ok
                user = user[:-1]
            _add(user)

        for m in RE_NTLMv2_HASH.finditer(texto):
            _add(m.group(1))
            dom = m.group(2)
            if dom and self._parece_login_simples(dom):
                # NetBIOS domain em user::DOMAIN:… — não é login pessoa
                pass

        for m in RE_SMTP_USER_EXISTS.finditer(texto):
            u = m.group(1)
            if u.casefold() in SMTP_USER_NAO_CONTA:
                continue
            chave = u.casefold()
            if chave not in vistos:
                vistos.add(chave)
                candidatos.append(u)
        for m in RE_VRFY_USER.finditer(texto):
            u = m.group(1)
            if u.casefold() in SMTP_USER_NAO_CONTA:
                continue
            chave = u.casefold()
            if chave not in vistos:
                vistos.add(chave)
                candidatos.append(u)
        for m in RE_ENV_USERNAME.finditer(texto):
            _add(m.group(1))

        # Dump mysql.user / módulo mysql_sql (login na 1ª coluna)
        if re.search(r"(?i)\bmysql\.user\b|\bmysql_sql\b", texto):
            for m in RE_MYSQL_USER_ROW.finditer(texto):
                _add(m.group(1))

        achados: list[Achado] = []
        for user in candidatos:
            for m in re.finditer(
                rf"\b{re.escape(user)}\b", texto, flags=re.IGNORECASE
            ):
                achados.append(
                    Achado(
                        real_value=texto[m.start() : m.end()],
                        entity_type="USER",
                        start=m.start(),
                        end=m.end(),
                        camada="regex",
                    )
                )
        return achados

    def _achados_senhas(self, texto: str) -> list[Achado]:
        """
        Senhas: DOMAIN\\user:pass, -p/-w/--password, Password:,
        user / senha, host - senha, user%senha (rpcclient -U).
        Propaga o valor em todas as ocorrências exatas (mesma string no texto).
        """
        senhas: list[str] = []
        vistos: set[str] = set()

        def _add_senha(bruto: str) -> None:
            s = (bruto or "").strip().strip("'\"")
            if not s or not self._eh_password_cliente(s):
                return
            chave = s.casefold()
            if chave in vistos:
                return
            vistos.add(chave)
            senhas.append(s)

        for m in RE_NXC_DOM_USER_PASS.finditer(texto):
            # secretsdump DOMAIN\user:rid:lmhash:nthash::: → hashes, não senha monólito
            if self._eh_hash_secretsdump_tail(m.group(2)):
                continue
            _add_senha(m.group(2))

        for m in RE_IMP_SLASH_USER_PASS.finditer(texto):
            if m.group(1).casefold() in SPN_SERVICOS:
                continue
            if re.search(r"[=&\[]", m.group(3) or ""):
                continue
            _add_senha(m.group(3))

        for m in RE_CLI_PASSWORD.finditer(texto):
            bruto = next((g for g in m.groups() if g), None)
            if bruto:
                _add_senha(bruto)

        for m in RE_SLASH_FLAG_PASS.finditer(texto):
            _add_senha(m.group(1))

        for m in RE_PASS_LABEL.finditer(texto):
            s = m.group(1)
            if self._parece_senha(s) or self._eh_password_cliente(s):
                _add_senha(s)

        for m in RE_ENV_SECRET.finditer(texto):
            nome, valor = m.group(1), m.group(2).strip().strip("'\"")
            if not valor:
                continue
            _add_senha(valor)

        for m in RE_USER_SLASH_PASS.finditer(texto):
            s = m.group(2)
            if self._parece_senha(s):
                _add_senha(s)

        for m in RE_DASH_PASSWORD.finditer(texto):
            s = m.group(1)
            if self._parece_senha(s):
                _add_senha(s)

        # rpcclient -U 'user%pass' / DOMAIN/user%pass
        for m in RE_PCT_PASSWORD.finditer(texto):
            _add_senha(m.group(1))

        achados: list[Achado] = []
        vistos_span: set[tuple[int, int]] = set()
        for senha in sorted(senhas, key=len, reverse=True):
            for m in re.finditer(re.escape(senha), texto):
                start, end = m.start(), m.end()
                if (start, end) in vistos_span:
                    continue
                vistos_span.add((start, end))
                achados.append(
                    Achado(
                        real_value=texto[start:end],
                        entity_type="PASSWORD",
                        start=start,
                        end=end,
                        camada="regex",
                    )
                )
        return achados

    def _achados_hashes_secrets(self, texto: str) -> list[Achado]:
        """NTLM (secretsdump) + hex longo (bootKey / dpapi / ticket)."""
        achados: list[Achado] = []
        vistos: set[tuple[int, int]] = set()

        def _add(start: int, end: int, tipo: str = "PASSWORD") -> None:
            if (start, end) in vistos or end <= start:
                return
            val = texto[start:end]
            if not self._token_mapeavel(val, tipo):
                return
            # LM/NT vazios conhecidos ainda mascaram (não vazar formato do dump)
            vistos.add((start, end))
            achados.append(
                Achado(
                    real_value=val,
                    entity_type=tipo,
                    start=start,
                    end=end,
                    camada="regex",
                )
            )

        for m in RE_SAM_HASH.finditer(texto):
            _add(m.start(3), m.end(3))
            _add(m.start(4), m.end(4))

        for m in RE_NTLMv2_HASH.finditer(texto):
            # challenge, ntproof, av/blob
            _add(m.start(3), m.end(3))
            _add(m.start(4), m.end(4))
            _add(m.start(5), m.end(5))

        # DOMAIN\user:rid:lm:nt::: quando NXC não consumiu a senha
        for m in RE_NXC_DOM_USER_PASS.finditer(texto):
            tail = m.group(2)
            if not self._eh_hash_secretsdump_tail(tail):
                continue
            # extrai os dois hashes de 32 hex
            hm = re.match(
                r"(?i)^\d+:([0-9a-f]{32}):([0-9a-f]{32})",
                tail,
            )
            if not hm:
                continue
            base = m.start(2)
            _add(base + hm.start(1), base + hm.end(1))
            _add(base + hm.start(2), base + hm.end(2))

        for m in RE_HEX_SECRET.finditer(texto):
            val = m.group(1)
            # só hex / 0xhex
            if not re.fullmatch(r"(?i)(?:0x)?[0-9a-f]+", val):
                continue
            _add(m.start(1), m.end(1))

        return achados

    def _achados_nomes_paren(self, texto: str, eng: dict[str, Any]) -> list[Achado]:
        """Nomes completos em (Nome Sobrenome) — ex.: (Marina Braga)."""
        achados: list[Achado] = []
        vistos: set[str] = set()
        for m in RE_NOME_PAREN.finditer(texto):
            nome = m.group(1).strip()
            chave = nome.casefold()
            if chave in vistos:
                continue
            if self._na_allow_lista(nome, eng) or ALLOW_TECNICO.search(nome):
                continue
            if self._eh_jargao_share_ou_rotulo(nome):
                continue
            if not self._token_mapeavel(nome, "PERSON"):
                continue
            vistos.add(chave)
            # Propaga o nome completo no texto
            for m2 in re.finditer(re.escape(nome), texto):
                achados.append(
                    Achado(
                        real_value=texto[m2.start() : m2.end()],
                        entity_type="PERSON",
                        start=m2.start(),
                        end=m2.end(),
                        camada="regex",
                    )
                )
        return achados

    def _achados_full_name_field(
        self, texto: str, eng: dict[str, Any]
    ) -> list[Achado]:
        """Full Name: / Display Name: / JSON displayname — rpcclient, BloodHound."""
        achados: list[Achado] = []
        vistos: set[str] = set()

        def _considerar(nome: str) -> None:
            nome = (nome or "").strip()
            if not nome or nome.startswith(("TARGET_", "PERSON_", "CLIENT_")):
                return
            if nome.upper() in {
                "REDACTED FOR PRIVACY",
                "REDACTED",
                "N/A",
            }:
                return
            chave = nome.casefold()
            if chave in vistos:
                return
            if self._na_allow_lista(nome, eng) or ALLOW_TECNICO.search(nome):
                return
            if self._eh_jargao_share_ou_rotulo(nome):
                return
            if not self._token_mapeavel(nome, "PERSON"):
                return
            # Precisa cara de nome (espaço) ou display curto não-jargão
            if " " not in nome and not re.fullmatch(
                r"[A-ZÁÉÍÓÚ][a-záéíóúâêôãõàç]+", nome
            ):
                return
            vistos.add(chave)
            for m2 in re.finditer(re.escape(nome), texto):
                achados.append(
                    Achado(
                        real_value=texto[m2.start() : m2.end()],
                        entity_type="PERSON",
                        start=m2.start(),
                        end=m2.end(),
                        camada="regex",
                    )
                )

        for m in RE_FULL_NAME_FIELD.finditer(texto):
            _considerar(m.group(1))
        for m in RE_NOME_LISTA_CARGO.finditer(texto):
            _considerar(m.group(1))
        for m in RE_JSON_DISPLAYNAME.finditer(texto):
            _considerar(m.group(1))
        for m in RE_NOME_ANTES_EMAIL.finditer(texto):
            _considerar(m.group(1))
        for m in RE_NOME_ADMIN_LOCAL.finditer(texto):
            _considerar(m.group(1))
        for m in RE_META_AUTHOR_NOME.finditer(texto):
            _considerar(m.group(1))
        return achados

    def _achados_sids(self, texto: str) -> list[Achado]:
        """Domain SID AD (S-1-5-21-…) — identifica o domínio do cliente."""
        achados: list[Achado] = []
        for m in re.finditer(r"\bS-1-5-21-\d+(?:-\d+){2,}\b", texto):
            achados.append(
                Achado(
                    real_value=m.group(),
                    entity_type="SID",
                    start=m.start(),
                    end=m.end(),
                    camada="regex",
                )
            )
        return achados

    def _achados_regex(
        self, texto: str, eng: dict[str, Any] | None = None
    ) -> list[Achado]:
        eng = eng or {}
        achados: list[Achado] = []
        for m in RE_IPV4.finditer(texto):
            ip = m.group()
            if ip in IPV4_NAO_MASCARAR:
                continue
            achados.append(
                Achado(ip, "IP", m.start(), m.end(), "regex")
            )
        for m in RE_IP_MYSQL_CURINGA.finditer(texto):
            achados.append(
                Achado(m.group(1), "IP", m.start(1), m.end(1), "regex")
            )
        for m in RE_CNPJ.finditer(texto):
            achados.append(
                Achado(m.group(), "ID", m.start(), m.end(), "regex")
            )
        for m in RE_PHONE.finditer(texto):
            achados.append(
                Achado(m.group(), "PHONE", m.start(), m.end(), "regex")
            )
        for m in RE_CERT_ST.finditer(texto):
            val = m.group(1).strip()
            if val and val.lower() not in {"br", "us", "uk", "n/a"}:
                achados.append(
                    Achado(val, "ADDRESS", m.start(1), m.end(1), "regex")
                )
        for m in RE_WHOIS_STREET.finditer(texto):
            val = m.group(1).strip()
            if val and val.upper() not in {"REDACTED", "REDACTED FOR PRIVACY", "N/A"}:
                achados.append(
                    Achado(val, "ADDRESS", m.start(1), m.end(1), "regex")
                )
        for m in RE_WHOIS_POSTAL.finditer(texto):
            val = m.group(1).strip()
            if val and val.upper() not in {"REDACTED", "N/A"}:
                achados.append(
                    Achado(val, "ADDRESS", m.start(1), m.end(1), "regex")
                )
        for m in RE_WHOIS_CITY.finditer(texto):
            val = m.group(1).strip()
            if val and val.upper() not in {"REDACTED", "REDACTED FOR PRIVACY", "N/A"}:
                achados.append(
                    Achado(val, "ADDRESS", m.start(1), m.end(1), "regex")
                )
        for m in RE_GITLEAKS_SECRET.finditer(texto):
            segredo = m.group(1).strip().strip("'\"")
            if segredo and self._token_mapeavel(segredo, "APIKEY"):
                achados.append(
                    Achado(
                        segredo,
                        "APIKEY",
                        m.start(1),
                        m.start(1) + len(segredo),
                        "regex",
                    )
                )
        for m in RE_EMAIL.finditer(texto):
            email = m.group()
            if self._eh_upn_ad(email):
                # BloodHound USER@DOMAIN.LOCAL → USER + DOMAIN, não EMAIL
                local, _, dominio = email.partition("@")
                local_ok = (
                    self._eh_username_cliente(local, eng)
                    and local.casefold()
                    not in {
                        "admins",
                        "users",
                        "guests",
                        "computers",
                        "controllers",
                    }
                )
                if local_ok:
                    achados.append(
                        Achado(
                            local, "USER", m.start(), m.start() + len(local), "regex"
                        )
                    )
                if dominio and not self._dominio_publico(dominio):
                    achados.append(
                        Achado(
                            dominio,
                            "DOMAIN",
                            m.start() + len(local) + 1,
                            m.end(),
                            "regex",
                        )
                    )
                continue
            local, _, dominio = email.partition("@")
            # E-mail de vendor/tool (edge-security.com) não é cliente
            if dominio and self._dominio_publico(dominio):
                continue
            achados.append(
                Achado(email, "EMAIL", m.start(), m.end(), "regex")
            )
        for m in RE_URL.finditer(texto):
            host = self._host_de_url(m.group())
            if not host or self._dominio_publico(host) or self._eh_lixo(host):
                continue
            if not self._dominio_do_cliente(host, eng):
                continue
            achados.append(
                Achado(host, "DOMAIN", m.start(), m.end(), "regex")
            )
        # API keys / tokens (lista fixa — sempre mascarar)
        for m in RE_APIKEY.finditer(texto):
            segredo = next((g for g in m.groups() if g), None)
            if not segredo or not self._token_mapeavel(segredo, "APIKEY"):
                continue
            start = m.start(0) + m.group(0).rfind(segredo)
            achados.append(
                Achado(segredo, "APIKEY", start, start + len(segredo), "regex")
            )
        # Domínios livres: NÃO varrer a internet inteira.
        # Só reforça: TLD interno OU FQDN do scope (inclui .br do cliente).
        for m in RE_FQDN.finditer(texto):
            val = self._normalizar_span_dominio(m.group())
            if not val or self._dominio_publico(val) or self._eh_lixo(val):
                continue
            if ALLOW_TECNICO.search(val):
                continue
            baixo = val.lower()
            if any(baixo.endswith(ext) for ext in EXTENSOES_NAO_DOMINIO):
                continue
            interno = baixo.endswith(
                (".local", ".lan", ".internal", ".corp", ".intranet")
            )
            if interno or self._dominio_do_cliente(val, eng):
                grupo = m.group()
                idx = grupo.lower().find(val.lower())
                if idx < 0:
                    continue
                achados.append(
                    Achado(
                        val,
                        "DOMAIN",
                        m.start() + idx,
                        m.start() + idx + len(val),
                        "regex",
                    )
                )
        achados.extend(self._achados_usernames(texto, eng))
        achados.extend(self._achados_senhas(texto))
        achados.extend(self._achados_hashes_secrets(texto))
        achados.extend(self._achados_nomes_paren(texto, eng))
        achados.extend(self._achados_full_name_field(texto, eng))
        achados.extend(self._achados_sids(texto))
        return achados

    @staticmethod
    def _eh_upn_ad(email: str) -> bool:
        """True se parece UPN/BloodHound (user@ad.local), não SMTP público."""
        e = (email or "").strip().casefold()
        if "@" not in e:
            return False
        dominio = e.rsplit("@", 1)[-1]
        return any(dominio.endswith(tld) for tld in TLD_UPN_AD)

    @staticmethod
    def _host_de_url(url: str) -> str | None:
        m = re.match(r"https?://([^/:]+)", url, re.IGNORECASE)
        return m.group(1) if m else None

    @staticmethod
    def _token_ao_redor(texto: str, start: int, end: int) -> str:
        """Expande o span até o token (letras/dígitos/._-) — evita URL parcial."""
        i = start
        while i > 0 and (texto[i - 1].isalnum() or texto[i - 1] in "._-"):
            i -= 1
        j = end
        while j < len(texto) and (texto[j].isalnum() or texto[j] in "._-"):
            j += 1
        return texto[i:j]

    # --- Camada 3: Presidio ---

    def _achados_presidio(
        self, texto: str, eng: dict[str, Any] | None = None
    ) -> list[Achado]:
        if not self._presidio_ok or not self._analyzer:
            return []
        try:
            results = self._analyzer.analyze(
                text=texto,
                language="en",
                score_threshold=PRESIDIO_SCORE,
            )
        except Exception:
            return []

        eng = eng or {}
        achados: list[Achado] = []
        for r in results:
            tipo = MAPA_PRESIDIO.get(r.entity_type)
            if not tipo:
                continue
            trecho = texto[r.start : r.end].strip()
            if not trecho or self._eh_lixo(trecho):
                continue
            # NER não pode atravessar linha (whois Name + Organization)
            if "\n" in trecho:
                continue
            if not self._token_mapeavel(trecho, tipo):
                continue
            if self._parece_senha(trecho):
                continue
            if ALLOW_TECNICO.search(trecho):
                continue
            if self._na_allow_lista(trecho, eng):
                continue
            # theHarvester: NER engole "Searching Bing" inteiro
            if tipo == "PERSON" and re.match(r"(?i)searching\b", trecho):
                continue
            # Chave de .env / dump PHP — não é nome de pessoa
            if tipo == "PERSON" and re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", trecho):
                continue
            if re.search(
                r"(?i)(?:\$_)?(?:ENV|SERVER|GET|POST|COOKIE|REQUEST)\s*\[",
                trecho,
            ):
                continue
            if tipo in {"PERSON", "ORG"} and re.search(r"\[['\"]", trecho):
                continue
            if re.search(
                r"(?i)\b(?:Registrant|Organization|Expiry|Registry|"
                r"Registrar|Jump\s+host|Meta-Author)\b",
                trecho,
            ):
                continue
            if self._eh_rotulo_http_ou_scan(trecho):
                continue
            if tipo == "DOMAIN":
                trecho = self._normalizar_span_dominio(trecho)
                if not trecho:
                    continue
            if tipo == "DOMAIN" and not self._dominio_do_cliente(trecho, eng):
                continue
            if self._eh_jargao_share_ou_rotulo(trecho):
                continue
            # Span de coluna smbmap/enum (padding) — replace destrói a linha
            if re.search(r"\s{2,}", trecho):
                continue
            if re.search(
                r"(?i)\b(?:READ|WRITE|ONLY|NO\s+ACCESS|Permissions|Disk|Comment|"
                r"Home\s+Drive|Profile\s+Path|Primary\s+Group|Full\s+Name|User\s+Name)\b",
                trecho,
            ):
                continue
            # Rótulos rpcclient inteiros
            if re.fullmatch(
                r"(?i)Home\s+Drive|Profile\s+Path|Primary\s+Group|"
                r"Full\s+Name|User\s+Name|Domain\s+SID|Domain\s+Name",
                trecho,
            ):
                continue
            # Vários logins juntos (homes: a b c) — Presidio não engole o bloco
            partes = trecho.split()
            if tipo in {"PERSON", "ORG"} and len(partes) >= 2:
                if all(
                    re.fullmatch(r"[a-z][a-z0-9._-]{2,32}", p) for p in partes
                ):
                    continue
            # Presidio URL corta ticket.kirbi → ticket.ki (.ki = TLD); olha o token inteiro
            token_cheio = self._token_ao_redor(texto, r.start, r.end)
            if tipo == "DOMAIN":
                baixo_tok = token_cheio.lower()
                if any(baixo_tok.endswith(ext) for ext in EXTENSOES_NAO_DOMINIO):
                    continue
                if self._na_allow_lista(token_cheio, eng):
                    continue
            if tipo == "DOMAIN" and self._dominio_publico(trecho):
                continue
            if tipo == "DOMAIN" and any(
                trecho.lower().endswith(ext) for ext in EXTENSOES_NAO_DOMINIO
            ):
                continue
            if tipo == "ORG" and self._dominio_publico(trecho):
                continue
            # Span LDAP DN destruído (Web App,OU → PERSON)
            if "," in trecho or "OU=" in trecho.upper() or "CN=" in trecho.upper():
                continue
            if re.search(r"(?i)\bAdmin(?:istrator)?\b", trecho) and " " in trecho:
                continue
            # BloodHound / SharpHound / Rubeus labels
            if re.fullmatch(
                r"(?i)SharpHound|BloodHound|LocalAdmin|LocalAdmins|Trusts|"
                r"Container|ObjectProps|DomainController|HasSession|"
                r"Group|Session|ACL|RDP|SPN|Users|Computers|"
                r"Responder|ntlmrelayx|Poisoners|LLMNR|NBT-NS|MDNS|"
                r"NTLMv2(?:-SSP)?|Cleartext|WORKGROUP|SMBD-Relay|"
                r"Rubeus|kerbrute|Hydra|Helm|Kerberoasting|Ask\s+TGT|Web\s+App|"
                r"SQL\s+Service|http-post-form|https-post-form|mysql_sql",
                trecho,
            ):
                continue
            # LSA secret service names _SC_MSSQLSERVER
            if re.fullmatch(r"(?i)_?SC_[A-Za-z0-9_]+", trecho) or re.fullmatch(
                r"(?i)MSSQLSERVER", trecho
            ):
                continue
            # Cabeçalhos Impacket / verbs
            if re.fullmatch(
                r"(?i)Querying|LastLogon|PasswordLastSet|MemberOf|"
                r"ServicePrincipalName|Name|Email|UAC",
                trecho,
            ):
                continue
            # Não mascarar versões tipo "2.4.41"
            if re.fullmatch(r"[\d.]+", trecho):
                continue
            # Fragmentos de MAC / hex curto — não são PERSON
            if re.fullmatch(r"[0-9a-f]{2}(?::[0-9a-f]{2})*", trecho, re.I):
                continue
            # Span sujo nmap: hex MAC misturado com ldap/rootdse / script (|_)
            if re.search(r"(?i)ldap|rootdse", trecho) and (
                re.search(r"[0-9a-f]{2}", trecho, re.I)
                or "|" in trecho
                or "\n" in trecho
            ):
                continue
            # Recalcula span no texto limpo (primeira ocorrência do trecho no range)
            start = texto.find(trecho, r.start, r.end + 1)
            if start < 0:
                start = r.start
            achados.append(
                Achado(trecho, tipo, start, start + len(trecho), "presidio")
            )
        return achados

    @staticmethod
    def _na_allow_lista(valor: str, eng: dict[str, Any]) -> bool:
        """Allow dinâmica (aprendizado permanente / allowed=)."""
        chave = (valor or "").casefold().strip()
        if not chave:
            return False
        for termo in eng.get("allow_list") or []:
            t = (termo or "").casefold().strip()
            if not t:
                continue
            if chave == t:
                return True
            # Só frases (com espaço): cobre sub-span do NER sem
            # 'sqlsvc' ⊂ 'mssqlsvc' (falso positivo).
            if " " in t and t in chave:
                return True
            if " " in chave and chave in t:
                return True
        return False

    # --- Merge sem overlap (prioridade: blocklist > regex > presidio) ---

    @staticmethod
    def _merge(achados: list[Achado]) -> list[Achado]:
        # Mesmo start: blocklist > regex > presidio (evita NER engolir vários logins)
        ordem_camada = {"blocklist": 0, "regex": 1, "presidio": 2}
        ordenados = sorted(
            achados,
            key=lambda a: (
                a.start,
                ordem_camada.get(a.camada, 9),
                -len(a.real_value),
            ),
        )
        escolhidos: list[Achado] = []
        ultimo_fim = -1
        for a in ordenados:
            if a.start < ultimo_fim:
                continue
            escolhidos.append(a)
            ultimo_fim = a.end
        return escolhidos

    def sanitizar(
        self,
        texto: str,
        repo: Any,
        engagement_id: int,
        eng: dict[str, Any],
        *,
        persistir_rascunho: bool = True,
    ) -> ResultadoSanitize:
        """
        Roda o pipeline. Se persistir_rascunho=True, grava novos mapeamentos
        na hora (CANCEL deve reverter via descartar_rodada).
        """
        camada1 = self._achados_blocklist(texto, eng)
        camada1.extend(
            self._achados_mapa_existente(texto, repo, engagement_id, eng)
        )
        camada2 = self._achados_regex(texto, eng)
        camada3 = self._achados_presidio(texto, eng)
        fundidos = [
            a
            for a in self._merge(camada1 + camada2 + camada3)
            if not self._eh_lixo(a.real_value)
            and (
                a.camada == "blocklist"
                or a.entity_type in {"USER", "PASSWORD", "EMAIL", "APIKEY"}
                or not self._na_allow_lista(a.real_value, eng)
            )
        ]

        if not fundidos:
            return ResultadoSanitize(
                texto_original=texto,
                texto_sanitizado=texto,
                teve_sensivel=False,
            )

        # Agrupa por valor real. Domínio/e-mail: maiúscula não muda o ident.
        contagem: dict[str, dict[str, Any]] = {}
        for a in fundidos:
            if a.entity_type in {"DOMAIN", "HOST", "EMAIL", "ORG"}:
                chave = a.real_value.casefold()
            else:
                chave = a.real_value
            if chave not in contagem:
                contagem[chave] = {
                    "real_value": a.real_value,
                    "entity_type": a.entity_type,
                    "count": 0,
                    "positions": [],
                }
            contagem[chave]["count"] += 1
            contagem[chave]["positions"].append((a.start, a.end))

        novos: list[dict[str, Any]] = []
        increments: list[tuple[int, int]] = []
        mapa_replace: dict[str, str] = {}
        resumo: list[dict[str, Any]] = []

        for _chave, info in contagem.items():
            real = info["real_value"]
            if not self._token_mapeavel(real, info["entity_type"]):
                continue
            placeholder, criado, mid = ph.obter_ou_criar(
                repo, engagement_id, real, info["entity_type"]
            )
            mapa_replace[real] = placeholder
            if criado and persistir_rascunho:
                repo.inserir_mapeamento(
                    engagement_id,
                    real,
                    placeholder,
                    info["entity_type"],
                    occurrence_count=0,  # sobe no ACEPT
                )
                row = repo.buscar_por_valor_real(engagement_id, real)
                novos.append(
                    {
                        "id": row["id"] if row else None,
                        "real_value": real,
                        "placeholder": placeholder,
                        "entity_type": info["entity_type"],
                        "count": info["count"],
                    }
                )
                mid = row["id"] if row else None
            elif mid is not None:
                increments.append((mid, info["count"]))
                novos.append(
                    {
                        "id": mid,
                        "real_value": real,
                        "placeholder": placeholder,
                        "entity_type": info["entity_type"],
                        "count": info["count"],
                        "ja_existia": True,
                    }
                )
            else:
                novos.append(
                    {
                        "id": None,
                        "real_value": real,
                        "placeholder": placeholder,
                        "entity_type": info["entity_type"],
                        "count": info["count"],
                    }
                )

            resumo.append(
                {
                    "real": real,
                    "placeholder": placeholder,
                    "times": info["count"],
                    "type": info["entity_type"],
                }
            )

        # Substitui do mais longo para o mais curto (evita partial).
        # Tokens alfanuméricos: fronteira de palavra — não destroem base64/ticket.
        texto_out = texto
        for real in sorted(mapa_replace.keys(), key=len, reverse=True):
            pholder = mapa_replace[real]
            if re.fullmatch(r"[A-Za-z0-9._$-]+", real):
                if pholder.startswith("CLIENT_NAME"):
                    # Marca colada (MareClaraPortal). Não come FQDN (nyxlynx.internal).
                    texto_out = re.sub(
                        rf"(?<![A-Za-z0-9_]){re.escape(real)}(?![a-z0-9_]|\.)",
                        pholder,
                        texto_out,
                        flags=re.IGNORECASE,
                    )
                else:
                    texto_out = re.sub(
                        rf"(?<![A-Za-z0-9_]){re.escape(real)}(?![A-Za-z0-9_])",
                        pholder,
                        texto_out,
                        flags=re.IGNORECASE,
                    )
            else:
                texto_out = texto_out.replace(real, pholder)

        # Linhas de ticket/base64: também limpa segredo colado SEM fronteira
        # (ex.: ...Bo1cmendesHELIOSCLINICA... em lab/dumps)
        texto_out = self._limpar_segredos_em_tickets(texto_out, mapa_replace)

        return ResultadoSanitize(
            texto_original=texto,
            texto_sanitizado=texto_out,
            resumo=resumo,
            novos_mapeamentos=novos,
            increments=increments,
            teve_sensivel=True,
        )

    @staticmethod
    def _limpar_segredos_em_tickets(
        texto: str, mapa_replace: dict[str, str]
    ) -> str:
        """Em linhas de ticket/base64, aplica replace até dentro de blobs colados."""
        if not mapa_replace:
            return texto
        out: list[str] = []
        for linha in texto.splitlines(keepends=True):
            if re.search(
                r"(?i)base64|kirbi|\.ccache|ticket in|ticket\.kirbi",
                linha,
            ):
                for real in sorted(mapa_replace.keys(), key=len, reverse=True):
                    if len(real) < 4:
                        continue
                    linha = re.sub(
                        re.escape(real),
                        mapa_replace[real],
                        linha,
                        flags=re.IGNORECASE,
                    )
            out.append(linha)
        return "".join(out)

    def confirmar_rodada(self, repo: Any, resultado: ResultadoSanitize) -> None:
        """ACEPT: confirma ocorrências e log."""
        for item in resultado.novos_mapeamentos:
            mid = item.get("id")
            if mid is None:
                continue
            if item.get("ja_existia"):
                repo.incrementar_ocorrencia(mid, item["count"])
            else:
                # zera estava 0; define contagem real
                repo.incrementar_ocorrencia(mid, item["count"])

    def descartar_rodada(self, repo: Any, resultado: ResultadoSanitize) -> None:
        """CANCEL: remove mapeamentos novos desta rodada; não toca nos antigos."""
        ids_novos = [
            item["id"]
            for item in resultado.novos_mapeamentos
            if item.get("id") is not None and not item.get("ja_existia")
        ]
        repo.remover_mapeamentos_ids(ids_novos)
