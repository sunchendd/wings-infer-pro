# G.FUN.02 设计函数时，优先使用返回值而不是输出参数

- **规则ID**：d40f344c-7f1d-4978-88e9-fdaeefbdbad0
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

使用输出参数的方式返回数据会导致代码可读性可维护性变差。

Go语言采用了多返回值的方式，这种方式可以让函数返回多个值，而不是只有一个返回值。

因此，优先使用多返回值的方式，可以让代码更加简洁、易读、易维护。

**【正确示例】**

```
##### 场景1：使用输出参数的方式返回数据。
- 修复示例：不要使用输出参数，要使用返回值。

    ```go
    func nextInt(b []byte, i int) (value int, nextIndex int) { // 符合：返回多个需要的返回值
        for ; i < len(b) && !isDigit(b[i]); i++ {
        }
        x := 0
        for ; i < len(b) && isDigit(b[i]); i++ {
            x = x*10 + int(b[i]) - '0'
        }
        return x, i
    }

    func main() {
        b := []byte{'a', '1', '2', 'c'}
        for x, i := 0, 0; i < len(b); {
            x, i = nextInt(b, i)
            fmt.Println(x)
        }
    }
    ```


```
**【错误示例】**

```
##### 场景1：使用输出参数的方式返回数据。
- 错误示例：nextInt函数可从字节数组中的指定的位置开始扫描读取下一个整数值，并返回整数值以及下一个待读取的非整数字符的位置。整数值使用输出参数返回。

    ```go
    func isDigit(r byte) bool {
        return '0' <= r && r <= '9'
    }

    func nextInt(b []byte, i int, x *int) int { // 不符合：通过传入的指针"x"来修改外部实参值
        for ; i < len(b) && !isDigit(b[i]); i++ {
        }
        *x = 0
        for ; i < len(b) && isDigit(b[i]); i++ {
            *x = *x*10 + int(b[i]) - '0'
        }
        return i
    }

    func main() {
        b := []byte{'a', '1', '2', 'c'}
        for x, i := 0, 0; i < len(b); {
            i = nextInt(b, i, &x)
            fmt.Println(x)
        }
    }
    ```


```
**【修复建议】**

不要使用输出参数，要使用返回值。
