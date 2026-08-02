i = 1
d = 67

while d {
    c = i
    c %= 3
    g = 1
    if c {
    } else {
        print("Fizz")
        g = 0
    }
    c = i
    c %= 5
    if c {
    } else {
        print("Buzz")
        g = 0
    }

    if g {
        println(i)
    } else {
        println("")
    }
    i += 1
    d = i
    d -= 101
}