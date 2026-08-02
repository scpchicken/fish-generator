println("Hello, World!")
i = 0
while i < 10 {
    println(i)
    i += 1
}
c = getc()
while c - 1 {
    while c {
        putc(c)
        c = getc()
    }
    println("")
    c = getc()
}