i = 1

while i < 101 {
    g = 1
    if i % 3 < 1 {
        print("Fizz")
        g = 0
    }
    if i % 5 < 1 {
        print("Buzz")
        g = 0
    }

    if g {
        print(i)
    }
    println("")
    i += 1
}