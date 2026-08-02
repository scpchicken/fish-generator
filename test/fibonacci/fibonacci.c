arr = []

count = 10
a = 0
b = 1
ind = 0

while count {
    arr[ind] = a
    c = b
    b += a
    a = c
    ind += 1
    count -= 1
}

ind = 9
while ind {
    println(arr[ind])
    ind -= 1
}
println(arr[ind])