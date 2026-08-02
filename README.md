# fish-generator
hexagony generator but for fish

[Inspiration](https://github.com/btnlq/HexagonyGenerator)

### how to run

```bash
python3 fishgen.py hello.c # will create hello.z
python3 fish.py hello.z
python3 fish.py hello.z -- "first" "second"
```

### docs

```bash
# set variables
i = 1

# modify variables
i += 5

j = 3
i += j

# print without newline
print(i)
# print with newline
println(i)

# arrays
arr = [1, 2, 3]
arr[5] = 67
println(arr[5]) # 67

# print a char
c = 'q'
putc(c)

# get a char from ARGV (each arg ends with NUL byte, -1 sentinel after all args)
q = getc()

# if statements
if i {
    println(i)
} else {
    i += 5
    println(i)
}


# while loops
while i {
    j = i
    while j {
        j -= 1
        print("j: ")
        println(j)
    }

    print("\ni: ")
    println(i)
}
```