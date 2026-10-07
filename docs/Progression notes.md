# Project Progression Notes

## Histórico anterior (já registrado no repositório)

1. Nos primeiros dias não foram feitas anotações — o registro começou depois.

2. Início da migração da aplicação para uma imagem Docker, visando facilitar deploys e ter melhor controle do ambiente.
   - Criação do `Dockerfile`
   - Adaptação do `Dockerfile` para a aplicação: instalação das dependências via `requirements.txt`, exposição da porta 5001

3. **02/09/2026** — Estudo de PostgreSQL para incluir um banco de dados na aplicação.

4. **12/09/2026** — Execução manual da API e do Postgres para conectá-los. Objetivo: a aplicação armazenar as métricas da API no banco de dados.

### Fazendo os dois containers se conectarem

**Imagens:**
```
devops-lab % docker images
IMAGE ID       DISK USAGE   CONTENT SIZE   EXTRA
flaskapp:latest    1bd87f455a47   1.64GB   409MB
postgres:latest    4ef4dbc939d6   672MB    167MB
```

**Criação da rede customizada:**
```bash
docker network create mynetwork
```

**Subida inicial dos containers (com erros a corrigir depois):**
```bash
docker run -it -d -p 5432:5432 --name postgres --network mynetwork -e POSTGRES_PASSWORD=mypassword postgres:latest
docker run -it -d -p 8080:80 --name postgres --network mynetwork flaskapp:latest
```

---

## Continuação — Sessão de integração API ↔ Banco de Dados (12/09/2026)

### 1. Correções de sintaxe no `docker run`
- Ordem correta: flags do Docker sempre antes do nome da imagem
- `-e` precisa vir antes da imagem para funcionar como variável de ambiente
- `--name` precisa de um valor logo em seguida (não pode ser seguido direto de outra flag)

### 2. Rede e conectividade
- Nomes de container só funcionam como hostname em redes **customizadas** (`docker network create`), não na rede `bridge` padrão
- `docker network connect` permite conectar containers já em execução a uma rede existente
- Diferença entre `ping` (camada de rede/ICMP) e teste de porta real (`nc -zv`)
- `EXPOSE` no Dockerfile é apenas documentação — não substitui o `-p` do `docker run`

### 3. Criação da tabela de métricas no Postgres
```sql
CREATE TABLE requests (
    id bigserial PRIMARY KEY,
    event_type text,
    code varchar,
    url varchar,
    ip inet,
    created_at timestamptz DEFAULT now()
);
```
- `PRIMARY KEY` não é automático com `bigserial` — precisa ser declarado
- `DEFAULT now()` preenche o timestamp automaticamente
- `timestamptz` (com timezone) preferido a `timestamp` para evitar problemas futuros

### 4. Ajustes no `Dockerfile`
- Base trocada de `python3:latest` (inválida) para `python:slim`
- Corrigido uso de `apt-get` (não `apt`) — mais estável para uso em scripts/automação
- Adicionado `COPY test_db.py /` para o script de teste de conexão

### 5. Dependências (`requirements.txt`)
```
flask==3.0.3
psycopg2-binary==2.9.12
```

### 6. Script de teste de conexão isolado (`test_db.py`)
- Testado dentro do container `flaskapp`, validando conexão container→container com o `postgres`
- Confirmado retorno de dados da tabela `requests` via `psycopg2`

### 7. Integração da lógica de métricas no `app.py`
- Adicionada função `get_connection()` (abre conexão usando variáveis de ambiente)
- Adicionada função `log_event()` (grava eventos na tabela `requests`, com `try/except` para não derrubar a aplicação em caso de falha do banco)
- Chamadas inseridas nas rotas `/shorten`, `/r/<code>` e nos error handlers 404/500
- Abordagem escolhida: abrir e fechar conexão a cada operação (mais simples, adequada à fase atual de aprendizado)

### 8. Build e deploy da versão integrada
```bash
docker build --no-cache -t flaskapp .
docker rm -f flaskapp
docker run -dti -p 8080:5001 --name flaskapp --network mynetwork \
  -e DB_HOST=postgres -e DB_PORT=5432 -e DB_NAME=postgres -e DB_USER=postgres -e DB_PASSWORD=mypassword \
  flaskapp
```

### 9. Erro identificado e lição aprendida
- Container em execução não refletia o `app.py` atualizado (causa: build/run usando imagem desatualizada ou cache)
- **Lição:** sempre validar com `docker exec -it <container> cat app.py | grep <termo>` antes de assumir que a atualização "pegou"
- Build sem `-t` gera imagem "dangling" (sem nome) — sempre nomear a imagem com `-t` para não confundir com a tag antiga

### 10. Testes end-to-end
```bash
curl http://localhost:8080/health
curl -X POST http://localhost:8080/shorten -H "Content-Type: application/json" -d '{"url": "https://www.exemplo.com"}'
curl -i http://localhost:8080/r/CODIGO
curl -i http://localhost:8080/r/naoexiste123
curl http://localhost:8080/stats
docker exec -it postgres psql -U postgres -c "SELECT * FROM requests;"
```

---

## Próximos passos sugeridos
- [ ] Confirmar que os eventos de todas as rotas (`shorten`, `redirect`, `404`, `500`) estão sendo gravados corretamente na tabela `requests`
- [ ] Avaliar se a criação da tabela deve ser automatizada (script de inicialização) em vez de manual via `psql`
- [ ] Migrar a execução manual para `docker-compose.yml` (Fase 3 do roadmap)
- [ ] Explorar Prometheus + Grafana como alternativa/complemento ao armazenamento direto em Postgres (Fase 6 do roadmap)