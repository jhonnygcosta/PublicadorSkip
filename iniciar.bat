@echo off
chcp 65001 >nul
title Publicador Skip
cd /d "%~dp0"

rem Primeira vez (ou depois de mudar a interface): monta o frontend
if not exist "frontend\dist\index.html" (
  echo Preparando a interface pela primeira vez...
  pushd frontend
  call npm install --no-audit --no-fund || goto erro
  call npm run build || goto erro
  popd
)

python -c "import fastapi, uvicorn, requests, dotenv" 2>nul || (
  echo Instalando dependencias do Python...
  python -m pip install -r backend\requirements.txt || goto erro
)

echo.
echo  Publicador Skip rodando em http://localhost:8765
echo  Deixe esta janela aberta enquanto envia. Fechar = parar o envio.
echo.
start "" http://localhost:8765
cd backend
python -m uvicorn app:app --host 127.0.0.1 --port 8765
goto :eof

:erro
echo.
echo Algo deu errado acima. Tire um print desta janela.
pause
