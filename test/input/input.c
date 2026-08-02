println("Hello, World!")
c = getc()
d=c
d += 1

while d {
    println("iter")
    while c {
        println("You entered:")
        putc(c)
        println("")
        c = getc()
    }
    c = getc()
    d = c
    d += 1
}

println("done")