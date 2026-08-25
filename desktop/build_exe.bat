@echo off
REM build_exe.bat
REM Construit l'executable Windows PointageQR.exe avec PyInstaller.
REM A executer sur Windows, depuis le dossier du projet, avec Python installe.
REM Utilise "python -m ..." plutot que les commandes pip/pyinstaller seules,
REM pour eviter les soucis de PATH (dossier Scripts non ajoute au PATH).

echo === Installation des dependances ===
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo === Construction de l'executable ===
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name PointageQR ^
    --collect-all cv2 ^
    main.py

echo.
echo === Termine ===
echo L'executable se trouve dans le dossier dist\PointageQR.exe
pause
