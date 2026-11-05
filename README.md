# Publicador Skip

Aplicação web para organizar e agendar a publicação de Reels em Páginas do Facebook usando a Meta Graph API.

O projeto possui uma interface em React + TypeScript (Vite) e uma API em Python (FastAPI). O backend prepara a fila de vídeos, envia os arquivos para a Meta, agenda as publicações e acompanha o processamento.

> **Status:** esta versão foi estruturada para execução local no Windows. Ela ainda não está pronta para deploy em hospedagem cloud. Veja [Limitações para deploy na nuvem](#limitações-para-deploy-na-nuvem).

## Funcionalidades

- Configuração do ID da Página do Facebook e do token de acesso.
- Validação das credenciais com a Meta.
- Leitura de arquivos `.mp4` de uma pasta local.
- Geração de prévia da agenda antes do envio.
- Definição da data e do horário inicial, intervalo entre vídeos e quantidade por dia.
- Campo para legenda padrão e suporte a arquivo `.txt` com o mesmo nome do vídeo.
- Envio de Reels pela Meta Graph API.
- Agendamento de publicações.
- Acompanhamento do progresso de envio e do processamento.
- Histórico local de vídeos enviados/agendados.
- Tentativa de retomada de envios interrompidos e repetição de falhas temporárias.
- Consulta e cancelamento de publicações agendadas, conforme suporte da API.

## Tecnologias

**Frontend**
- React
- TypeScript
- Vite
- Tailwind CSS

**Backend**
- Python
- FastAPI
- Uvicorn
- Requests
- python-dotenv

**Integração**
- Meta Graph API — publicação de Reels em Página do Facebook.

## Estrutura do projeto

```text
publicador-skip/
├── backend/
│   ├── app.py
│   ├── motor.py
│   ├── requirements.txt
│   └── .env.exemplo
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
├── .gitignore
├── iniciar.bat
└── README.md
```

## Requisitos

- Windows 10 ou 11.
- Python 3.10 ou superior.
- Node.js LTS e npm.
- Uma Página do Facebook administrada pela conta que fornecerá as credenciais.
- Aplicativo Meta configurado com as permissões necessárias para publicar Reels na Página.

Confira a documentação e os requisitos atuais da Meta antes de configurar a integração:  
https://developers.facebook.com/docs/

## Instalação e execução local

1. Clone o repositório:

   ```bash
   git clone https://github.com/SEU-USUARIO/SEU-REPOSITORIO.git
   cd SEU-REPOSITORIO
   ```

2. Crie o arquivo de configuração a partir do exemplo:

   ```bat
   copy backend\.env.exemplo backend\.env
   ```

3. Abra `backend\.env` e preencha as credenciais:

   ```env
   FB_PAGE_ID=ID_DA_SUA_PAGINA
   FB_PAGE_TOKEN=TOKEN_DE_ACESSO_DA_PAGINA
   ```

   Não compartilhe esse arquivo e não envie tokens para o GitHub.

4. Execute `iniciar.bat`.

   Na primeira execução, o script instala as dependências do frontend e gera a versão de produção da interface. Também instala as dependências Python, se necessário.

5. Acesse:

   http://localhost:8765

Mantenha a janela do terminal aberta enquanto o sistema estiver em uso. Fechar essa janela encerra o servidor e interrompe tarefas que ainda estejam em execução.

### Instalação manual

Se preferir iniciar os serviços manualmente, na raiz do projeto execute:

```bash
cd frontend
npm install
npm run build
```

Em outro terminal:

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8765
```

A interface compilada em `frontend/dist` é servida pelo próprio FastAPI.

## Configuração da Meta

O backend utiliza estas variáveis:

| Variável | Finalidade |
|---|---|
| `FB_PAGE_ID` | ID da Página do Facebook que receberá as publicações. |
| `FB_PAGE_TOKEN` | Token de acesso da Página, com as permissões necessárias. |
| `FB_APP_ID` | ID do aplicativo Meta; usado no fluxo auxiliar de geração/troca de token. |
| `FB_APP_SECRET` | Chave secreta do aplicativo Meta; usada no fluxo auxiliar de geração/troca de token. |
| `FB_USER_TOKEN` | Token de usuário temporário usado no fluxo auxiliar de geração/troca de token. |

As três últimas variáveis são opcionais para a operação normal quando `FB_PAGE_TOKEN` já está configurado. Consulte `backend/.env.exemplo` para o modelo.

**Segurança:** nunca publique tokens, App Secret, IDs privados ou arquivos `.env`. Se uma credencial real for enviada acidentalmente ao GitHub, revogue-a e gere outra.

## Arquivos de vídeo e legendas

Na versão local, o backend acessa diretamente os arquivos do computador onde o servidor está rodando.

- Os vídeos devem estar em formato `.mp4`.
- Para usar uma legenda específica, crie um arquivo `.txt` com o mesmo nome do vídeo.
- Exemplo:

```text
video-01.mp4
video-01.txt
video-02.mp4
video-02.txt
```

Quando não existir um `.txt` correspondente, o sistema utiliza a legenda padrão informada na interface.

O motor também utiliza `ffprobe`, quando disponível no sistema, para verificar características técnicas do vídeo antes do envio.

## Limitações para deploy na nuvem

**Não faça deploy desta versão esperando que ela funcione sem adaptações.** O código atual depende de recursos da máquina local:

- A interface envia ao backend o caminho de uma pasta do computador.
- O backend procura os vídeos no sistema de arquivos da máquina onde está executando.
- O seletor de pastas usa `tkinter`, que abre uma janela no computador do servidor — comportamento incompatível com uma aplicação hospedada.
- O histórico é salvo em `backend/historico_api.json`, um arquivo local que pode ser perdido em ambientes com armazenamento efêmero.
- A fila de trabalho e o estado da tarefa ficam em memória; reiniciar o processo pode interromper o trabalho e perder o estado em andamento.

Para uma versão cloud, será necessário adaptar o fluxo para:

1. O navegador enviar os vídeos para armazenamento de objetos, como Cloudflare R2, por upload direto ou URL pré-assinada.
2. O backend trabalhar com identificadores/URLs dos arquivos armazenados, em vez de caminhos locais do Windows.
3. O histórico e os agendamentos serem persistidos em banco de dados.
4. O processamento em segundo plano utilizar uma fila e um worker persistente.
5. Os tokens serem armazenados com segurança como variáveis de ambiente ou em um mecanismo próprio de gestão de segredos.
6. A aplicação implementar autenticação e controle de acesso antes de ficar pública.

A arquitetura cloud ainda precisa ser implementada; Render, Railway, R2 e PostgreSQL são opções possíveis, não serviços já integrados nesta versão.

## Segurança e Git

O arquivo `.gitignore` exclui arquivos locais e dados sensíveis, incluindo:

- `backend/.env`
- `backend/historico_api.json`
- `backend/historico_api.json.tmp`
- `__pycache__/`
- `node_modules/`
- `frontend/dist/`

Antes de enviar o projeto ao GitHub, confira o que será incluído:

```bash
git status
```

Se `backend/.env` ou outro arquivo com credenciais já tiver sido adicionado ao controle de versão, apenas incluí-lo no `.gitignore` não remove o arquivo do histórico. Remova-o do índice e revogue qualquer segredo que tenha sido publicado.

## Desenvolvimento do frontend

Para iniciar o servidor de desenvolvimento do Vite:

```bash
cd frontend
npm install
npm run dev
```

O Vite utiliza a porta `5754` e encaminha as chamadas `/api` para `http://127.0.0.1:8765`. Portanto, o backend precisa estar iniciado separadamente.

Para gerar a versão de produção:

```bash
cd frontend
npm run build
```

## Aviso

Este projeto utiliza a Meta Graph API e depende das permissões, limites, políticas e condições de uso definidos pela Meta. A disponibilidade de recursos e os requisitos de publicação podem mudar. O uso da ferramenta não garante aprovação ou publicação de conteúdo pela plataforma.

---

Desenvolvido para uso operacional da equipe Skip.
