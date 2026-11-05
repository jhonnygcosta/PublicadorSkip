@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Subir Publicador para o GitHub

where git >nul 2>nul || (echo Instale o Git: https://git-scm.com/download/win & pause & exit /b)

if not exist ".git" (
  git init -b main
  git remote add origin https://github.com/jhonnygcosta/PublicadorSkip.git
)

git config user.name >nul 2>nul || git config user.name "Jhonny"
git config user.email >nul 2>nul || git config user.email "jhonny@rg.com.br"
git add -A
echo.
echo Conferindo se nenhum segredo vai junto...
git diff --cached --name-only | findstr /i /r "\.env$ contas\.json historico_api" && (
  echo ERRO: arquivo com token na lista. Nada foi enviado.
  pause & exit /b
)

git commit -m "Publicador: varios influenciadores (Diogo, Mosca), gerador de token e correcao da escolha de pasta"
git push -u origin main || (
  echo.
  echo Se o repositorio no GitHub ja tinha arquivos, rode:  git pull origin main --allow-unrelated-histories
  echo e depois este .bat de novo.
)
pause
