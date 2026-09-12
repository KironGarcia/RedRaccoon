# Racoon-Mask — Mapa Completo de Construção e Arquitetura

Documento **único** de verdade do projeto. Substitui os mapas anteriores (obsoletos).  
Tudo o que foi definido na conversa de design com o Sensei está aqui.

**Idioma da UI do app:** English  
**SO alvo (v1):** Linux (executable)  
**Fase atual de construção:** esqueleto com interface real (placeholder de avatar) → depois pele/avatar

---

## 1. Por que existe

Em engagements reais, o scope pode proibir enviar dados do cliente para modelos de IA em cloud. Quebrar isso é quebrar contrato, confiança e reputação.

Racoon-Mask é um **filtro local de confidencialidade**: sanitiza outputs de pentest **antes** de irem para Cursor/qualquer IA em cloud, e reconstrói a resposta depois. Assim o pentester mantém assistência de IA forte sem enviar identificadores do cliente a terceiros.

Não é “IA local fraca no lugar do agente”. É o **intermediário rápido** entre o terminal e a cloud.

---

## 2. Princípios de produto

1. **Rápido** — poucos cliques; a app não deve roubar tempo do fluxo de trabalho.
2. **Determinístico** — sem LLM na sanitização (v1): regex + blocklist + Presidio/spaCy.
3. **Auditável** — código limpo e legível para o cliente abrir e verificar.
4. **Mínima retenção** — workspace com DB de cliente; queima explícita no fechamento; cobrança se sessão antiga/suja.
5. **Compacta** — janela pequena (canto inferior do desktop), convivendo com browser + Cursor.
6. **Humano no loop** — resumo + ACEPT / CANCEL; nunca envia sozinha para a cloud.

---

## 3. Metodologia de código limpo (“casa japonesa”)

O código é parte do argumento comercial e ético: *“verifique você mesmo”*.

### Obrigatório

- **Uma casa, muitos cômodos:** pastas por responsabilidade; nada solto na raiz sem motivo.
- **Blocos etiquetados:** cada módulo/função com nome e comentários curtos em português que digam *o que mora ali* e *por quê*.
- **Separação clara:** UI ≠ pipeline de sanitização ≠ persistência ≠ clipboard ≠ lifecycle da sessão.
- **Legível por não-especialista:** alguém sem ser senior deve conseguir seguir o fluxo lendo pastas e cabeçalhos.
- **Minimalismo visual no código:** arquivos curtos quando possível; sem “barraco” de funções misturadas.
- **Pronto para auditoria:** o cliente recebe o código e consegue apontar: aqui mascara IP, aqui grava mapeamento, aqui queima a DB.

### Proibido na construção

- Juntar tudo num único arquivo monstro.
- Nomes opacos (`do_stuff`, `tmp2`, `x`).
- Lógica de negócio escondida dentro de widgets da UI.
- Documentos/avulsos espalhados sem pasta.

### Metáfora operacional

Entrar no repositório deve parecer **casa japonesa minimalista** (ar fresco, ordem, cada coisa no lugar) — nunca **barraco empilhado** (medo de pisar e cair).

---

## 4. Stack técnico (v1)

| Peça | Escolha |
|------|---------|
| Linguagem | Python |
| UI | PySide6 (desktop Qt) — *Flet era o plano inicial; trocado na construção porque o runtime Flet exige `libmpv.so.1` incompatível com Kali rolling sem root* |
| Detecção | Microsoft Presidio + spaCy (`en_core_web_sm` ou equivalente leve) |
| Padrões estruturados | Regex (IPs, emails, URLs, hashes, etc.) — custom recognizers no Presidio quando couber |
| Persistência | SQLite **dentro do workspace do engagement** |
| Clipboard | `pyperclip` (ler e escrever) |
| Empacotamento | Executable Linux (PyInstaller / equivalente do stack) |
| LLM na sanitização | **Não** na v1 |

Sem credenciais de API. Tudo local.

---

## 5. Estrutura de pastas do projeto (alvo)

Organização sob `Racoon-Mask/` (ajustar nomes finos na implementação, manter o espírito):

```
Racoon-Mask/
├── docs/                      # Única documentação de arquitetura
│   └── MAPA_CONSTRUCAO.md     # Este arquivo
├── app/                       # Entrada da aplicação
│   └── main.py
├── core/                      # Coração determinístico (sem UI)
│   ├── sanitize.py            # Pipeline: blocklist → regex → Presidio
│   ├── reconstruct.py         # Placeholder → valor real
│   ├── placeholders.py        # Geração consistente TARGET_IP_1, etc.
│   └── queries.py             # Lookup, add-to-blocklist, replace em arquivos
├── db/                        # Schema e acesso SQLite
│   ├── schema.py
│   └── repository.py
├── session/                   # Workspace, dirty/clean, burn
│   ├── workspace.py
│   └── lifecycle.py
├── ui/                        # Só apresentação e eventos
│   ├── window.py              # Janela compacta, X, layout
│   ├── raccoon.py             # Avatar placeholder + balão
│   ├── dialogs.py             # Fluxos de fala (wizard, resumo, avisos)
│   └── theme.py               # Cores/estilo retro minimal
├── assets/                    # Imagens (placeholder agora; avatar depois)
├── workspaces/                # Workspaces locais (DB por engagement) — runtime
├── requirements.txt
└── README.md                  # Só se Kiron autorizar; preferir docs/ como fonte
```

Regra: **documentos de design ficam em `docs/`**. Nada de `.md` de arquitetura solto na raiz.

---

## 6. As 5 camadas do pipeline (ordem)

1. **Blocklist do engagement** (prioridade máxima, match exato) — nomes, domínios, hosts, IPs que o usuário cadastrou.
2. **Regex** — padrões estruturados (IP, email, URL, hash, domínio em formato padrão).
3. **Presidio + spaCy NER** — nomes/orgs em texto livre.
4. **LLM local verificador** — **fora da v1**.
5. **Confirmação humana** — resumo no balão + ACEPT / CANCEL.

### O que SEMPRE mascarar

- IPs (quando relevantes ao cliente/scope)
- Hostnames, domínios, subdomínios do cliente
- Nome da empresa e variantes
- Nomes de pessoas / contatos
- Emails corporativos
- Domínios AD / qualquer item da blocklist

### O que NUNCA mascarar (não quebrar análise da IA)

- Versões de software (`Apache 2.4.41`)
- Nomes de tecnologias, frameworks, protocolos
- Status HTTP, headers genéricos
- CVEs e nomes de vulnerabilidades conhecidas

### Placeholders

Formato: `{TYPE}_{N}` — exemplos: `TARGET_IP_1`, `TARGET_HOST_1`, `TARGET_DOMAIN_1`, `CLIENT_NAME`, `PERSON_1`.

**Mesmo valor real → mesmo placeholder** dentro do engagement (consistência entre vários PAST INPUT).

Lógica: consultar `entity_mapping` — se o valor real já tem placeholder neste eng, **reutilizar**; senão, criar novo incrementando o contador daquele `entity_type`.

Novas entidades detectadas **preenchem a tabela automaticamente** (o schema é fixo; os dados crescem com o uso).

---

## 6.1 Onde usar o Racoon no engagement (contexto operacional)

### Alto uso (ativar com frequência)

- Information Gathering passivo (whois, Shodan, theHarvester, DNSdumpster, certificados)
- Information Gathering ativo / enumeração (nmap, nikto, gobuster, enum4linux, SNMP)
- Resultados de exploração com dados reais (dumps SQLMap, credenciais crackeadas, etc.)
- Construção do relatório final (replace em massa de placeholders → valores reais)

### Uso pontual (não constante)

- Comandos de exploração montados à mão — muitas vezes já nascem com placeholder direto, sem passar pelo pipeline completo a cada linha

Isto não muda o código do core; orienta **quando** o intermediário vale o clique.

---

## 6.2 Fine-tuning / personalização do Presidio

Resposta à pergunta “dá para controlar e afinar?” — sim. Na implementação:

### a) Custom Recognizers

Registrar no motor do Presidio padrões regex próprios (ex.: formato de hostname interno dos relatórios, ID de funcionário do cliente, etc.).

### b) Score threshold

Cada detecção traz score de confiança (0–1).  
Subir o umbral → mais estrito (menos falso positivo, risco de deixar passar algo).  
Baixar → mais agressivo (mais coisas tapadas, menor risco de fuga).

**Política do Racoon-Mask:** errar para o lado **agressivo** — melhor tapar a mais do que a menos (alvo mental ~alta taxa de acerto / baixa fuga).

### c) Deny-list / Allow-list dinâmica por engagement

É a Capa 1 em código: valores de `engagement_config` / blocklist tipada injetados como match exato de **máxima prioridade** antes (ou acima) do NER genérico.

### d) Exclusão explícita (allow de análise técnica)

Lista de “não tocar”: versões de software, CVEs, protocolos, nomes de tecnologias — para o Presidio **não** marcar como sensível mesmo com match parcial.

Regex de padrões estruturados (IPs, emails, URLs, hashes MD5/SHA, domínios) pode rodar standalone ou como recognizer custom dentro do Presidio.

---

## 7. Schema SQLite (por workspace/engagement)

Um engagement ativo por vez (sem engs paralelos na v1).  
A DB vive **dentro do workspace** desse engagement.

### DDL de referência

```sql
CREATE TABLE engagement_config (
    id INTEGER PRIMARY KEY,
    engagement_name TEXT,       -- nome interno do workspace/trabalho
    client_name TEXT,           -- ex.: "Acme Corp"
    client_name_variants TEXT,  -- JSON list: ["Acme", "AcmeCorp", "acme-corp"]
    domains TEXT,               -- JSON list: ["acme.com", "acme.net"]
    ip_ranges TEXT,             -- JSON list: ["192.168.2.0/24"] ou IPs/hosts
    known_contacts TEXT,        -- JSON list de nomes, se houver
    created_at TIMESTAMP,
    active BOOLEAN              -- só um engagement ativo por vez
);

CREATE TABLE entity_mapping (
    id INTEGER PRIMARY KEY,
    engagement_id INTEGER,      -- FK a engagement_config
    real_value TEXT,            -- "192.168.2.3"
    placeholder TEXT,           -- "TARGET_IP_1"
    entity_type TEXT,           -- "IP" | "DOMAIN" | "ORG" | "PERSON" | "EMAIL" | "HOST"
    first_seen TIMESTAMP,
    occurrence_count INTEGER,   -- para o resumo "(47 times)"
    UNIQUE(engagement_id, real_value)
);

CREATE TABLE sanitization_log (
    id INTEGER PRIMARY KEY,
    engagement_id INTEGER,
    timestamp TIMESTAMP,
    action TEXT,                -- "sanitize" | "reconstruct"
    entities_processed INTEGER
);
-- Contém relação com dados reais por design.
-- Proteger como dado de cliente; some na queimada do workspace.
```

### Sessão dirty/clean

Arquivo ou flag de sessão (ex.: `session.flag`) no workspace:

- Ao abrir eng com sucesso → marca **dirty**
- Fechamento limpo após decisão de burn/keep → marca **clean** (ou apaga workspace se burn)
- Se a app achar workspace **dirty** na abertura (crash / PC desligou) → Racoon cobra limpeza primeiro

---

## 8. Interface (esqueleto já “com cara de app”)

### Tamanho e lugar

- Janela **compacta**, baixa altura — encaixa no espaço inferior do desktop (como no sketch: abaixo de browser/Cursor).
- Não é tool fullscreen.

### Elementos (English)

| Elemento | Função |
|----------|--------|
| **X** (canto) | Fechar → fluxo de burn (ver §10) |
| **Avatar** | Placeholder v1: bola com olho; depois arte do Racoon |
| **Speech bubble** | Única área de “fala” / output do Racoon (wizard, resumo, avisos, respostas) |
| **ACEPT** / **CANCEL** | Aparecem no balão quando há decisão pendente |
| **Questions box** | Input curto: respostas do wizard, comandos, consultas |
| **Send (círculo)** | Envia o texto do box (mesmo efeito que **Enter**) |
| **PAST INPUT** | Lê clipboard → processa na hora → mostra resumo (sem botão Sanitize) |

### Questions box — limite e anti-erro

- **Limite de caracteres baixo** (ex.: 200–400): cabe wizard, `ip {…}`, lookup; **não** cabe output de scan.
- Se o texto parecer scan/tool output (muitas linhas, padrões tipo `Nmap scan report`, bloco enorme) → **recusar** e Racoon avisar em inglês, por exemplo: *Use PAST INPUT for scan output. This box is for short questions/commands only.*
- Objetivo: forçar o caminho certo e evitar erro humano de colar scan no box errado.

### O que a UI **não** mostra

- Blocos gigantes de nmap/scan na tela. Entrada e saída bruta ficam no clipboard; na UI só resumo + diálogo.

### Estética v1 (esqueleto)

- Visual retro/minimal escuro + balão claro + botões azuis (como no sketch).
- Pronto para receber “pele” (avatar, pixel art fino) sem reescrever o core.

---

## 9. Fluxos de interação

### 9.1 Primeira abertura / novo engagement (wizard no balão)

Tudo via **balão pergunta → usuário responde no Questions box** (Send ou Enter).

1. Racoon: pergunta o **nome do workspace / engagement**.
2. Racoon: pede dados de confidencialidade e **mostra o formato obrigatório** para salvar certo, por exemplo:

   ```text
   Please add confidential items using this format:
   ip {client_ip}
   host {client_host}
   domain {client_domain}
   name {person_or_company}
   ```

   Motivo: lista solta tipo `190.22.0.1, pedro, tecline` não dá para classificar com segurança.

3. Usuário envia linhas no formato; app grava na blocklist/tabelas.
4. Racoon: *ready to start — paste your first input to mask when you want.*

### 9.2 PAST INPUT (fluxo principal)

1. Usuário copia output no terminal (Ctrl+C).
2. Clica **PAST INPUT**.
3. App lê clipboard (`pyperclip.paste()`), roda o pipeline, **não** exibe o texto completo.
4. Balão mostra **só o resumo** (ex.: `192.168.2.3 → TARGET_IP_1 (47×)`).
5. **ACEPT** → confirma e **copia automaticamente** o texto sanitizado para o clipboard → mensagem tipo *Copied to clipboard*.
6. **CANCEL** → **descarta tudo desta rodada**; **nada** dessa saída entra/permanece como resultado aceito na DB de mapeamento daquela operação (entrada mal colada / usuário desistiu). Não copia nada.

### 9.3 Nenhum dado sensível encontrado

Racoon no balão: *No sensitive data found to change. You can share this input safely.*

- **ACEPT** → copia o texto original (inalterado) para o clipboard.
- **CANCEL** → descarta; não copia.

Sem inventar função extra: mesmo padrão ACEPT/CANCEL.

### 9.4 Questions box (durante o eng)

Serve para:

1. **Respostas do wizard** e comandos curtos.
2. **Adicionar item à tabela de confidencialidade no meio do eng** (descobriu host/nome fora do fluxo e quer incluir nos próximos filtros) — comando/frase clara do tipo *add confidential …* com o mesmo formato `ip {}` / `host {}` / etc.
3. **Perguntar / colar comando** para devolver resultado com valores **reais** no lugar dos placeholders (lookup / reconstruct de trecho).
4. **Substituir placeholders em arquivo** de relatório (ver §11).

Não é chat com LLM. É parsing determinístico de intenção + DB.

Respeitar limite de caracteres e detecção anti-scan (§8). Scan → só **PAST INPUT**.

### 9.5 Um engagement por vez

Sem workspaces paralelos na v1. Terminou / queimou / trocou → um ativo só.

---

## 10. Retenção e queima da base

### Fechar (X)

1. Não fecha em silêncio.
2. Pergunta: **Burn database?**
3. Mensagem forte recomendando **YES** (evitar retenção de dado de cliente).
4. **YES** → apaga workspace/DB (queimada) e fecha.
5. **NO** → aviso chamando atenção + **mantém** a sessão/workspace para continuar depois (ex.: trabalho em vários dias).

### Reabertura com retenção

Mesmo após NO, na próxima abertura o Racoon continua **estrito**: lembra que há dado retido e reforça o cuidado (cultura anti-retenção).

### Crash / PC desligou (fechamento não limpo)

Workspace marcado **dirty**. Na próxima abertura, **primeira** mensagem: workspace antigo/sujo detectado → orientar **apagar e seguir** (ou fluxo equivalente de limpeza) antes de operar normal.

### Por que existe o NO

Só para o caso consciente: continuar o mesmo eng em dias seguintes sem recadastrar blocklist/mapeamentos. Não é o caminho padrão recomendado.

---

## 11. Relatórios: Markdown agora, Word depois

### v1

- Find-and-replace em arquivo **`.md`** (e texto puro): placeholders → valores reais via tabela.
- Adequado se o relatório intermediário usar placeholders.

### Word (`.docx`) — futuro, não bloqueia v1

- **Possível**, não impossível.
- Stack típico: `python-docx`.
- Dificuldade: **média** — no `.docx` o texto de um placeholder pode estar **partido em vários runs XML**; replace ingênuo falha; precisa lógica cuidadosa de junção/substituição.
- Encaixa no momento em que o relatório já está pronto e só falta automatizar a volta dos placeholders → nomes reais antes de ir a PDF.
- **PDF:** mais difícil (outra fase; não é o mesmo problema).

Decisão: **v1 = `.md` / texto**. **`.docx` = fase posterior** documentada aqui como desejada, sem implementar agora.

---

## 12. O que está FORA da v1

- OCR / screenshots
- LLM local como 2ª verificação
- MCP interceptando o chat do Cursor (inviável como interceptor automático do input box)
- Avatar/sprites animados finais (só placeholder bola-com-olho)
- Empacotamento Windows `.exe` (foco Linux primeiro)
- Edição nativa de `.docx` / PDF
- Múltiplos engagements em paralelo

---

## 13. Plano de fases de construção

### Fase 1 — Esqueleto polido (agora)

- Estrutura de pastas “casa japonesa”
- DB + workspace + dirty/clean + burn
- Pipeline sanitize/reconstruct + blocklist com formato tipado
- UI compacta completa (balão, ACEPT/CANCEL, questions com limite + anti-scan, PAST INPUT, X)
- Wizard de eng no balão
- Consultas básicas + add confidencial + replace `.md`
- Avatar placeholder
- `requirements.txt` + caminho para build Linux
- Código comentado/etiquetado para auditoria

### Fase 2 — Pele

- Avatar Racoon real
- Ajuste fino pixel/retro
- Polimento visual sem mudar o core

### Fase 3+ (opcional)

- Replace em `.docx`
- Calibragem fina Presidio com outputs reais de lab
- Cosméticos / animação

---

## 14. Critérios de “pronto para validar” (Fase 1)

- [ ] Criar eng pelo balão com formato `ip{}` / `host{}` / `domain{}` / `name{}`
- [ ] PAST INPUT mascara e mostra só resumo
- [ ] ACEPT copia sanitizado; CANCEL não persiste a rodada nem copia
- [ ] “Nenhum sensível” → msg + ACEPT copia original / CANCEL descarta
- [ ] Questions: lookup placeholder, add blocklist, replace `.md`; limite de chars + recusa se parecer scan
- [ ] X → Burn YES/NO com avisos
- [ ] Reabrir dirty → cobra limpeza
- [ ] Código organizado por pastas, auditável
- [ ] Roda em Linux; caminho claro para executable

---

## 15. Resumo das decisões travadas

| Tema | Decisão |
|------|---------|
| Sanitize button | Não existe — só PAST INPUT |
| Mostrar scan completo na UI | Não |
| MCP interceptor | Não |
| LLM no filtro | Não (v1) |
| Idioma UI | English |
| SO | Linux |
| Engs paralelos | Não |
| CANCEL | Descarta rodada; não grava/copia |
| Sem sensíveis | Mesmo ACEPT/CANCEL |
| Wizard | Formato tipado obrigatório no balão |
| Questions | Wizard + add confidencial + reconstruct + `.md` |
| Questions box | Limite 200–400 chars + recusa se parecer scan |
| Word | Depois (possível, médio) |
| Código | Casa japonesa, auditável |
| Docs antigos | Obsoletos — **este arquivo é a única fonte** |
| Sensei (pós-app) | Skill futura `trabalhar-com-racoon-mask` — ver `notas/` desta seção |

---

*Racoon-Mask — intermediário de confidencialidade; código limpo; retenção mínima; IA na cloud sem dado do cliente em claro.*
