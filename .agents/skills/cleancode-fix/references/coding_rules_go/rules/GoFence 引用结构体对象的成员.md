# GoFence 引用结构体对象的成员

- **规则ID**：df2afc26-42e5-44d0-b936-54ca664b938f
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

在函数间用指针传递，在获取返回指针的时候，切记要判断一下返回值是不是nil，否则造成空指针一直在被引用

**【正确示例】**

```
```
type P struct {
    Name string
    Age  int
}

func B(p *P) (np *P) {
    return
}
func main() {
    p := &P{}
    np := B(p)
    if np != nil { //正确： 对B函数的返回值进行了非空的判断
        fmt.Printf("%v", np.Name)
    }
}
```

```
**【错误示例】**

```
```
type P struct {
    Name string
    Age  int
}

func B(p *P) (np *P) {
    return
}
func main() {
    p := &P{}
    np := B(p)
    fmt.Printf("%v", np.Name) //错误 ：这里要判断B函数的返回值会不会是空值
}
```

```
**【修复建议】**

在引入前，对成员对象进行非空的判断处理------------------参考华为go语言编程规范3.1
