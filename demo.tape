Output assets/demo.gif
Set Shell bash
Set FontSize 16
Set Width 1200
Set Height 800
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms
Set Padding 20

Hide
Type `export PS1='$ ' && export PATH=/home/terence/code/acclaud/.venv/bin:/usr/bin:/bin`
Enter
Sleep 500ms
Type "cd /tmp && rm -rf acclaud-demo && mkdir acclaud-demo && cd acclaud-demo"
Enter
Sleep 1s
Type "clear"
Enter
Sleep 500ms
Show

Type "acclaud balance"
Sleep 500ms
Enter
Sleep 3s

Type "acclaud expenses"
Sleep 500ms
Enter
Sleep 3s

Type "acclaud report 2026-02"
Sleep 500ms
Enter
Sleep 4s

Type `cat "output/2026-02 Budget Report.md" | head -60`
Sleep 500ms
Enter
Sleep 5s
