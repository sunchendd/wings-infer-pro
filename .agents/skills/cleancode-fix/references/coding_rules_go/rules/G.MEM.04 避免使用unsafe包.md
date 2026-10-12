# G.MEM.04 避免使用unsafe包

- **规则ID**：d04cdd43-0bce-4711-9400-2d5e1750aa65
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

除指定的例外情形外，禁止使用uintptr与unsafe.Pointer编写函数。无分别的对所有的业务功能使用uintptr和unsafePointer编写业务代码，将可能带来缓冲区溢出等内存安全和资源泄漏等风险。



禁止的例子，如：用于处理网络数据的库函数接口中，参数大量的使用uintptr接收缓冲区输入。正确的方式，使用[]byte。

**【正确示例】**

```
func main() {
    inputPara := flag.String("inputPara", "0", "")
    flag.Parse()
    foo(*inputPara)
}
func foo(str string) {
    var tempBuf1 [8]byte
    var isOverWrite = []byte{0xFE, 0xFE, 0xFE, 0xFE, 0xFE, 0xFE, 0xFE, 0xFE}
    fmt.Printf("isOverWrite数组元素值全部为：
%v
", isOverWrite)
    var strLen = len(str)
    if strLen < 8 {
        for index, ch := range str{
            tempBuf1[index] = byte(ch)
        }
    }
    fmt.Printf("tempBuf1=%p
",&tempBuf1)
    fmt.Printf("
执行后，isOverWrite数组元素值实际上为：
%v", isOverWrite)
}

```
**【错误示例】**

```
func test_bad01() {
 a := [4]int{0, 1, 2, 3}
 p1 := unsafe.Pointer(&a[1])//告警，存在unsafe.Pointer
 p3 := unsafe.Pointer(uintptr(p1) + 2 * unsafe.Sizeof(a[0]))//告警，存在unsafe.Pointer和uintptr
 *(*int)(p3) = 6
 fmt.Println("a =", a) // a = [0 1 2 6]

 // ...

 type Person struct {
  name   string
  age    int
  gender bool
 }

 who := Person{"John", 30, true}
 pp := unsafe.Pointer(&who)//告警
 pname := (*string)(unsafe.Pointer(uintptr(pp) + unsafe.Offsetof(who.name)))  //告警
 page := (*int)(unsafe.Pointer(uintptr(pp) + unsafe.Offsetof(who.age))) //告警
 pgender := (*bool)(unsafe.Pointer(uintptr(pp) + unsafe.Offsetof(who.gender))) //告警
 *pname = "Alice"
 *page = 28
 *pgender = false
 fmt.Println(who) // {Alice 28 false}
}

```
**【修复建议】**

不要使用uintptr与unsafe.Pointer
