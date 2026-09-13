# template-benchmark

Como documentar os testes de Mask/Redactor do RedRaccoon, e o **mapa de tools** para montar blocos inventados nos próximos engs.

Não substitui `template-eng1` (carta de um eng já corrido). Este ficheiro é o **método** + o **catálogo** do que ainda falta cobrir.

---

## 1. Lei do número oficial

O número que compara eng × eng é **só a 1ª cola** — o Racoon como estava, antes de qualquer remendo desta evidência.

| Métrica | O que mede | Furo |
|---------|------------|------|
| **Cobertura (recall)** | Dos identificadores de cliente no output, quantos foram tapados | vazou |
| **Precisão** | Das máscaras aplicadas, quantas eram de fato cliente | falso positivo (comeu jargão/tool/versão) |
| **F1** | Média harmônica das duas | número único para lançamento / comparação |

- Unidade = **valor único** (o mesmo e-mail duas vezes conta 1).
- Erro de **rótulo** (empresa virar `PERSON_*` mas ainda mascarada) **não** baixa cobertura; anota-se em “rótulo”.
- Reteste depois do fix **não entra** na tabela oficial. Só prova que o remendo fechou *este* output.
- Barra de produto: **F1 ≥ 95% na 1ª cola**.
- `blocked=` / `allowed=`: o Sensei/agente **não** mete dado de cliente no fonte. Palavra coined (`nxl_edge`) → `blocked=` se o humano quiser. Tool/versão comida → `allowed=`.
- Padrão de **classe** (`DB_PASSWORD=`, `glpat-`, `hooks.slack.com/services/`) vai no `sanitize.py`. Identificador de cliente **nunca** vai no fonte.

Por tool (1ª cola) → média da fase. Mesmo formato em todo eng.

---

## 2. Estrutura de um eng de teste

Cada fase do pentest (IG passivo → ativo → enum → vuln → exploit → post-ex → relatório) leva **dois tipos de bloco**, nesta ordem:

### 2.1 Bloco A — dados sensíveis do kickoff (blocklist)

O que o “cliente” entregou no wizard. De propósito **pequeno** no black box (o resto o Racoon tem que achar sozinho).

```
ip=…
host=…          (opcional)
domain=…
name=…          (razão social, marca, pessoas)
email=…
```

Isto **não** é o scan. Vai no **Questions**, não no PAST INPUT.

### 2.2 Bloco B — scans / saídas inventadas (PAST INPUT ou reconstruct)

Uma tool (ou um comando) por bloco. Texto no formato **oficial** da tool (nmap, gobuster, hydra, curl, mysql_sql, …).

Misturar de propósito:

- Identificadores **já** na blocklist (o filtro deve reutilizar o mesmo placeholder).
- Identificadores **novos** (host, IP, pessoa, senha, token) — black box.
- Jargão que **não** pode virar placeholder (nome da tool, versão, CVE, `VRFY`, `nginx`, path `/.env`).

Fluxos:

| Momento | Onde cola | O que testa |
|---------|-----------|-------------|
| Tool output | Mask / PAST INPUT | sanitizar |
| Comando com `TARGET_*` | Mask / Questions `reveal` | reconstruct curto |
| Relatório com placeholders | Redactor / PAST REPORT | reconstruct do texto |

Ritual: 1ª cola **sem ACEPT** até validar → tabela F1 → remendo só por classe → reteste (nota, não oficial).

### 2.3 O que gravar depois de cada tool

1. O bloco inventado (inteiro).
2. Tabela: cobertura / precisão / F1 + vazou / FP / rótulo.
3. Média da **fase**.
4. Nota de **fix** (não é benchmark): o que mudou no código ou `allowed=`/`blocked=`.
5. Reteste: uma linha “fechou / não fechou nesta evidência”.

### 2.4 Mapa de fases (igual à metodologia)

| Fase | O que o bloco simula |
|------|----------------------|
| 1 IG passivo | whois, DNS, OSINT, leak em git |
| 2 IG ativo | nmap, WhatWeb, openssl/curl |
| 3 Enum | usuários, dirs, APIs |
| 4 Vuln | .env, nuclei, debug |
| 5 Exploit | presets Meta/hydra/curl + **outputs** |
| 6 Post-ex | só saídas internas (SQL, CI vars, Helm, VPN) |
| Relatório | PAST REPORT (F-01 / F-02) |

---

## 3. Mapa de tools — para inventar blocos

**Jr** = esperado num pentester júnior / eJPT / primeiro emprego (incluindo **comandos** do SO, não só “apps”).  
**Sr** = uso frequente em ops seniores (AD profundo, cloud, pivot, C2).  
**Ambos** = o júnior já toca; o sénior usa o tempo todo.

Não é lista de loja. É cobertura de **classe de output** para o Mask. Um bloco novo deve parecer a saída real da tool.

### 3.1 Information gathering — passivo / OSINT

| Tool / comando | Classe | Jr/Sr | Output típico a simular |
|----------------|--------|-------|-------------------------|
| `whois` | comando | Jr | Registro.br / IANA / ICANN (CNPJ, rua, telefone, pessoa) |
| `dig` / `host` / `nslookup` | comando | Jr | NS, MX, A, TXT, SOA |
| `curl` / `wget` | comando | Jr | HTML, JSON API, headers, arquivos |
| `openssl s_client` | comando | Jr | certificado (CN, O, e-mail, SAN) |
| browser / Google / crt.sh | OSINT | Jr | nomes, e-mails, subdomínios |
| theHarvester | tool | Jr | e-mails, hosts, people |
| `gitleaks` | tool | Jr | Secret:, Author:, AWS, senha em repo |
| `git clone` / `git log` / `git show` | comando | Jr | commit, autor, .env.example |
| Recon-ng | tool | Jr/Sr | módulos OSINT |
| `amass` / `subfinder` | enum DNS | Sr | subdomínios em massa |
| `httpx` / `naabu` | probe | Sr | hosts vivos, títulos |
| `gau` / `waybackurls` / `katana` | crawl OSINT | Sr | URLs históricas |
| `trufflehog` | leak | Sr | secrets em git (além do gitleaks) |
| Shodan / Censys (CLI ou web) | OSINT | Sr | banners, IPs, orgs |

### 3.2 Information gathering — ativo / mapping

| Tool / comando | Classe | Jr/Sr | Output típico a simular |
|----------------|--------|-------|-------------------------|
| `ping` / `traceroute` | comando | Jr | host up, hops |
| `nmap` (`-sV -sC`, scripts) | tool | Jr | ports, banners, ssl-cert, smtp-commands |
| WhatWeb | tool | Jr | Title, Email, Cookies, Meta-Author |
| `netcat` / `nc` / `ncat` | comando | Jr | banner SMTP/HTTP cru |
| `masscan` | scan | Sr | portas em massa |
| `rustscan` | scan | Sr | wrapper rápido de nmap |
| `arp-scan` / `netdiscover` | LAN | Jr/Sr | hosts internos (lab) |

### 3.3 Enumeration — serviços e pessoas

| Tool / comando | Classe | Jr/Sr | Output típico a simular |
|----------------|--------|-------|-------------------------|
| `gobuster` / `dirb` / `ffuf` | dirs | Jr | Status 200 `.env`, `debug.php` |
| `nikto` | web | Jr | headers, files |
| `smtp-user-enum` + `VRFY` | mail | Jr | `exists` / `does not exist` |
| `enum4linux` / `enum4linux-ng` | SMB | Jr | users, shares, OS |
| `smbclient` / `smbmap` | SMB | Jr | shares, permissões |
| `rpcclient` | RPC | Jr | `enumdomusers`, queryuser |
| `snmpwalk` | SNMP | Jr | sysDescr, users |
| `ldapsearch` | LDAP | Jr/Sr | displayName, sAMAccountName, mail |
| `showmount` | NFS | Jr | exports |
| `finger` / `rusers` | legado | Jr | users (lab antigo) |
| GitLab/GitHub API (`curl`) | API | Jr | JSON `username` / `name` |
| NetExec / CrackMapExec | AD/SMB | Sr | shares, users, SAM, winrm |
| Impacket `GetADUsers` / `GetUserSPNs` / `lookupsid` | AD | Sr | SPN, hashes, SID |
| BloodHound / SharpHound | AD graph | Sr | JSON, edges, LocalAdmin |
| `kerbrute` | Kerberos | Sr | userenum, passwordspray |
| `ldapdomaindump` | AD | Sr | dump de domínio |

### 3.4 Vulnerability analysis

| Tool / comando | Classe | Jr/Sr | Output típico a simular |
|----------------|--------|-------|-------------------------|
| `curl` `.env` / `debug.php` / `phpinfo` | comando | Jr | APP_KEY, DB_*, tokens |
| `nuclei` | templates | Jr/Sr | `[critical] files/env-file` |
| `searchsploit` / Exploit-DB | pesquisa | Jr | lista de exploits (não é scan) |
| nmap NSE (`vuln`, `vulners`) | script | Jr | CVEs no porto |
| Nikto (já acima) | web | Jr | misconfig |
| `testssl.sh` / `sslscan` | TLS | Jr/Sr | cipher, cert |
| Burp (issue list) | proxy | Sr | nomes de issue + URL do cliente |
| Nessus / OpenVAS | scanner | Sr | plugin, host, CVE |
| `kube-hunter` / `trivy` | k8s/container | Sr | cluster, image CVEs |
| Prowler / ScoutSuite / Pacu | cloud | Sr | AWS findings + account IDs |

### 3.5 Exploitation

| Tool / comando | Classe | Jr/Sr | Output típico a simular |
|----------------|--------|-------|-------------------------|
| Metasploit (`msfconsole`, `mysql_sql`, psexec, …) | framework | Jr/Sr | módulo, tabela SQL, session |
| `hydra` / `medusa` / `ncrack` | brute | Jr | `valid password found`, form `^USER^`/`^PASS^` |
| `sqlmap` | SQLi | Jr/Sr | dumped tables, users |
| `curl` com token / POST login | comando | Jr | JSON, Set-Cookie |
| `searchsploit` + PoC Python | exploit | Jr | output do PoC |
| Impacket `psexec` / `wmiexec` / `smbexec` | exec | Sr | shell Windows |
| `evil-winrm` | WinRM | Sr | PS session |
| `certipy` / Certify | AD CS | Sr | templates, auth |
| Responder / `ntlmrelayx` | relay | Sr | NTLMv2 hash, SUCCESS |
| custom nuclei / Burp extension | Sr | Sr | hit com host do cliente |

**Também testar reconstruct (Questions):** presets Meta/curl/hydra **com** `TARGET_*` — não só o output.

### 3.6 Post-exploitation

| Tool / comando | Classe | Jr/Sr | Output típico a simular |
|----------------|--------|-------|-------------------------|
| cliente `mysql` / `psql` | comando | Jr | SHOW DATABASES, SELECT users |
| `id` / `whoami` / `hostname` / `ip a` / `ifconfig` | comando | Jr | user, host, IPs internos |
| `cat` / `type` (Helm, ovpn, .env) | comando | Jr | yaml, VPN, secrets |
| GitLab CI variables (`curl` API) | API | Jr/Sr | JSON keys AWS/Slack |
| `linpeas` / `winpeas` | enum | Jr/Sr | bloco enorme (FP fácil) |
| Impacket `secretsdump` | dump | Sr | NTDS, SAM, hashes |
| Mimikatz / `lsassy` / `pypykatz` | cred | Sr | senhas em claro, tickets |
| Rubeus | Kerberos | Sr | TGT, kirbi |
| `hashcat` / `john` | crack | Sr | cracked user:pass |
| `chisel` / `ligolo-ng` / `proxychains` | pivot | Sr | tunel (pouco PII; hosts) |
| `kubectl` / kubeconfig | k8s | Sr | namespaces, secrets |
| `aws` CLI | cloud | Sr | account, buckets, keys |

### 3.7 Relatório / reconstruct

| Tool / comando | Classe | Jr/Sr | Output típico a simular |
|----------------|--------|-------|-------------------------|
| texto F-01 / F-02 com placeholders | Redactor | Jr | hallazgo WSTG/CVSS — PAST REPORT |
| `pandoc` / Word | doc | Jr | não é Mask; o Mask já reconstruiu |
| `replace` em `.md` (Questions) | app | Jr | ficheiro local do eng |

---

## 4. Como usar este mapa no próximo eng

1. Escolher a **fase**.
2. Pegar 2–4 tools **Jr** que ainda não têm bloco em `template-eng1` (buracos atuais: theHarvester, enum4linux, smb*, sqlmap, linpeas, searchsploit…).
3. Se o objetivo for puxar o filtro para sénior: 1–2 tools **Sr** (Impacket, BloodHound, Responder, nuclei cloud).
4. Escrever bloco A (blocklist curta) + blocos B no formato da tool.
5. Correr 1ª cola → preencher a tabela da secção 1.
6. Não copiar dado de cliente real para o fonte. Só classe de output.

### Buracos óbvios vs NyxLynx (`template-eng1`)

Já cobertos (exemplo): whois, dig, gitleaks, nmap, WhatWeb, openssl/curl, smtp-user-enum, gobuster, GitLab API, curl .env, nuclei, mysql_sql, hydra, Helm, OpenVPN, Redactor.

Ainda fracos / ausentes para o F1 de lançamento: **enum4linux / smbmap / ldapsearch / Impacket / BloodHound / Responder / sqlmap / linpeas / Burp issue / Nessus**. São as próximas cartas de teste, não desta instância.

---

## 5. Checklist de uma linha (colar na nota do eng)

```
Fase: _
Tool: _
1ª cola cobertura / precisão / F1: _ / _ / _
Vazou: _
FP (jargão/tool): _
blocked= / allowed= nesta cola: _
Remendo (classe, não cliente): _
Reteste (não oficial): passou / falhou
```
