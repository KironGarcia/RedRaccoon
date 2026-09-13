# Eng fictício — VesperOak

Simulação ponta a ponta do RedRaccoon (black box) como se fosse engagement real.  
**Carta do eng VesperOak — Mission 1 / slice Fase 1** (13/09/2026).  
Fases 2+ **não foram corridas** neste slice da missão.

**Cliente (invenção):** Vesper Oak Ltda — rede interna `.internal`, Campinas-SP. Nada disso existe.

**Como se lê o benchmark (lei)** — igual aos outros engs:

O número oficial de cada fase/tool é **só a 1ª cola**. Reteste depois do fix **não entra** na tabela de comparação; é só nota de que o remendo fechou *este* output.

| Métrica | O que mede |
|---------|------------|
| **Cobertura (recall)** | Dos identificadores de cliente no output, quantos foram tapados. Furo = vazou. |
| **Precisão** | Das máscaras aplicadas, quantas eram de fato cliente. Furo = falso positivo (comeu jargão). |
| **F1** | Média harmônica — número único para comparar fases/engs. |

Unidade = **valor único**. Barra de lançamento do produto: **F1 ≥ 95% na 1ª cola**.  
`blocked=` / `allowed=`: Sensei **não** cresce blocklist no meio do eng com string de cliente no fonte. Padrão de **classe** vai em `core/sanitize.py`.

---

## Scope / blocklist (o que o cliente entregou no kickoff)

Só isso — de propósito pequeno (Questions, não PAST INPUT):

```
ip=10.77.12.0/24
domain=vesperoak.internal
name=Vesper Oak Ltda
email=contato@vesperoak.internal
```

O resto (hosts novos, pessoas, e-mails, cookie, telefone, slug de path) o Racoon tinha que achar sozinho.

---

## Fase 1 — Information Gathering passivo

Ferramentas: **openssl** · **theHarvester** · **curl**

### 1.1 Bloco openssl (inventado)

```
$ openssl s_client -connect portal.vesperoak.internal:443 -servername portal.vesperoak.internal </dev/null 2>/dev/null | openssl x509 -noout -text
Certificate:
    Data:
        Version: 3 (0x2)
        Serial Number:
            5a:1c:9e:44:77:12:0a:bb
        Signature Algorithm: sha256WithRSAEncryption
        Issuer: C = BR, O = Let's Encrypt, CN = R11
        Validity
            Not Before: Aug  1 00:00:00 2026 GMT
            Not After : Oct 30 00:00:00 2026 GMT
        Subject: C = BR, ST = SP, L = Campinas, O = Vesper Oak Ltda, CN = portal.vesperoak.internal
        Subject Public Key Info:
            Public Key Algorithm: rsaEncryption
                Public-Key: (2048 bit)
        X509v3 extensions:
            X509v3 Subject Alternative Name:
                DNS:portal.vesperoak.internal, DNS:api.vesperoak.internal, DNS:mail.vesperoak.internal, email:ssl-admin@vesperoak.internal
            X509v3 Key Usage: critical
                Digital Signature, Key Encipherment
            X509v3 Extended Key Usage:
                TLS Web Server Authentication, TLS Web Client Authentication
```

### 1.2 Bloco theHarvester (inventado)

```
*******************************************************************
*  _   _                                            _             *
* | |_| |__   ___    /\  /\__ _ _ ____   _____  ___| |_ ___ _ __  *
* | __| '_ \ / _ \  / /_/ / _` | '__\ \ / / _ \/ __| __/ _ \ '__| *
* | |_| | | |  __/ / __  / (_| | |   \ V /  __/\__ \ ||  __/ |    *
*  \__|_| |_|\___| \/ /_/ \__,_|_|    \_/ \___||___/\__\___|_|    *
*                                                                 *
* theHarvester 4.6.0                                              *
* Coded by Christian Martorella                                   *
*******************************************************************

[*] Target: vesperoak.internal

[*] Searching Bing.
[*] Searching DuckDuckGo.
[*] Searching crtsh.

[*] Emails found: 6
---------------------
contato@vesperoak.internal
rh@vesperoak.internal
n.almeida@vesperoak.internal
j.ribeiro@vesperoak.internal
devops@vesperoak.internal
ssl-admin@vesperoak.internal

[*] Hosts found: 8
---------------------
portal.vesperoak.internal:10.77.12.20
api.vesperoak.internal:10.77.12.21
mail.vesperoak.internal:10.77.12.30
vpn.vesperoak.internal:10.77.12.40
git.vesperoak.internal:10.77.12.50
staging.vesperoak.internal:10.77.12.60
cdn.vesperoak.internal
www.vesperoak.internal

[*] People found: 3
---------------------
Nayara Almeida - PeopleSoft
Joao Ribeiro - LinkedIn
Marta Vos - crt.sh
```

### 1.3 Bloco curl (inventado)

```
$ curl -sI https://portal.vesperoak.internal/
HTTP/2 200
server: nginx/1.24.0
date: Sun, 13 Sep 2026 19:40:11 GMT
content-type: text/html; charset=utf-8
x-powered-by: Express
set-cookie: VO_SESSION=vo_sess_9f3a2c11b8e04d77; Path=/; HttpOnly; Secure
x-company: Vesper Oak Ltda
x-env: production
strict-transport-security: max-age=63072000; includeSubDomains

$ curl -s https://portal.vesperoak.internal/ | head -n 40
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>Portal Corporativo — Vesper Oak Ltda</title>
  <meta name="author" content="Nayara Almeida" />
  <meta name="description" content="Acesso interno Vesper Oak — helpdesk 19 3456-7788" />
  <link rel="canonical" href="https://portal.vesperoak.internal/" />
</head>
<body>
  <h1>Bem-vindo, colaboradores Vesper Oak</h1>
  <p>Suporte: helpdesk@vesperoak.internal | VPN: vpn.vesperoak.internal</p>
  <p>GitLab: https://git.vesperoak.internal/vesper-oak/portal.git</p>
  <!-- build: 1.8.4 | commit: a91c2ef | author: j.ribeiro@vesperoak.internal -->
</body>
</html>
```

### 1.4 Benchmark oficial — 1ª cola

| Tool | Cobertura | Precisão | F1 |
|------|-----------|----------|-----|
| openssl | 86% | 67% | **75%** |
| theHarvester | 96% | 100% | **98%** |
| curl | 58% | 100% | **73%** |
| **Fase 1 (oficial)** | **80%** | **89%** | **82%** |

**openssl — vazou:** `Campinas` (Subject `L=`).  
**openssl — comeu jargão:** `TLS Web Client Authentication` → CLIENT_NAME; `X509v3 Key Usage` → PERSON; `ST = SP` → CLIENT_NAME.  
**openssl — acertou:** domínios SAN/CN, org, partes de `ssl-admin@…`. Serial e `C=BR` não contados como ID de cliente.

**theHarvester — vazou:** `rh@` (local-part &lt; `MIN_CHARS_MAPEAVEL=4`; domínio mapeado).  
**theHarvester — precisão:** 0 FP de jargão (theHarvester / Bing / DuckDuckGo / crtsh / LinkedIn / PeopleSoft / Martorella intactos).  
**theHarvester — rótulo:** `n.almeida` / `j.ribeiro` / `devops` / `ssl-admin` como USER+DOMAIN (UPN `.internal`), não `TARGET_EMAIL_*` — não baixa cobertura.

**curl — vazou:** `helpdesk@` (local-part curto), `Nayara Almeida`, telefone BR `19 3456-7788`, cookie session value, slug `vesper-oak`.  
**curl — precisão:** máscaras = cliente (rótulo PERSON em “Vesper Oak” = rótulo, não FP de jargão); nginx / Express / HTTP2 / HSTS / build / commit intactos.

Preview sem ACEPT em todas as tools desta fase.

### 1.5 Fixes (não é benchmark)

Remendos por **classe** em `core/sanitize.py` (sem string de cliente no fonte):

| Erro da 1ª cola | Onde | Correção |
|-----------------|------|----------|
| `L = Campinas` vazou; `ST = SP` → CLIENT_NAME (Presidio) | `sanitize.py` | `RE_CERT_L` → ADDRESS; `RE_CERT_ST` ignora UF 2 letras; Presidio skip via `RE_CERT_ST_UF` / span UF |
| `X509v3 Key Usage` / EKU / `TLS Web Client Authentication` → PERSON/CLIENT_NAME | `sanitize.py` | `ALLOW_TECNICO` — X509 / EKU / TLS Web Server\|Client Authentication / Digital Signature / Key Encipherment / … |
| UPN curto (`rh@…`) não mapeava como USER | `sanitize.py` | fallback: local curto que falha gate USER → máscara o endereço inteiro como **EMAIL** |
| Telefone BR formatado (`DD NNNN-NNNN`) | `sanitize.py` | `RE_PHONE_BR` + `_eh_lixo` não descarta PHONE digit-only |
| HTML `<meta name="author" content="…">` | `sanitize.py` | `RE_HTML_META_AUTHOR` |
| Cookie session value (`VO_SESSION=…`) | `sanitize.py` | `RE_SET_COOKIE_PAIR` / `RE_SESSION_COOKIE_PAIR` — mascara só o **VALUE** |

### 1.6 Reteste (nota — não oficial)

Não entra na tabela de comparação. Prova que o remendo fechou *este* output:

| Tool | Reteste |
|------|---------|
| openssl | **PASS** all — Campinas→ADDR; ST=SP intacto; X509/EKU intactos; domains/org/user ok |
| theHarvester | **PASS** — `rh@`→EMAIL; people/IPs/hosts; jargão intacto |
| curl | **PASS** — telefone BR, cookie value, meta author, helpdesk@; slug `vesper-oak` → `blocked=` only (humano; sem classe estável no fonte) |

F1 oficial da Fase 1 permanece **82%**.

---

## Fases 2+ — não corridas neste slice

IG ativo, enum, vuln, exploit, post-ex e relatório **não** foram executados nesta missão (Mission 1 / Fase 1 only). Sem blocos, sem 1ª cola, sem fixes fora do escopo acima.
