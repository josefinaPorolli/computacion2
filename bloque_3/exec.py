import os

# Las variantes difieren en cómo especifican el programa y argumentos

# execl: argumentos como lista de parámetros
os.execl("/bin/ls", "ls", "-l", "/home")

# execlp: busca en PATH
os.execlp("ls", "ls", "-l", "/home")

# execle: permite especificar environment
os.execle("/bin/ls", "ls", "-l", env={"PATH": "/bin"})

# execv: argumentos como lista/tupla
os.execv("/bin/ls", ["ls", "-l", "/home"])

# execvp: busca en PATH + argumentos como lista
os.execvp("ls", ["ls", "-l", "/home"])

# execve: la más fundamental - path, args, env
os.execve("/bin/ls", ["ls", "-l"], {"PATH": "/bin"})
