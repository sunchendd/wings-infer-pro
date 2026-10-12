# GoFence 确保解引用unsafe.Pointer时不存在内存越界访问

- **规则ID**：b66d9fc3-6802-41ff-9f90-487dcff59675
- **更新时间**：2026-04-07 04:20:00

---

**【问题级别】**

一般

**【描述】**

指针在Go语言中是相对“安全”的，指针在正常的代码编写中无法指向任意的内存区域，可避免缓冲区溢出等内存越界访问的问题。在符合规则3.7例外的情况下，而使用unsafe.Pointer和uintptr方法可以绕过指针使用的限制，使得和C/C++中的指针用法和效果相似，使用不当会造成内存访问越界。在类型转换情形下，如果类型转换不正确，也可能导致溢出范围读写目标值。unsafe.Pointer可以将一个*T1值转换为类型*T2，其中T1和T2为两个任意类型。只有在T1的内存占用不大于T2并且此转换具有实际意义的时候才应该实施这样的转换。若转换后类型的内存更大，则会导致内存越界访问。

**【正确示例】**

```
```
func main() {
var ptra = new(uint8)
*ptra = 1
fmt.Printf("ptra=%d
", *ptra)
foo(unsafe.Pointer(ptra), 1)
}
func foo(buf unsafe.Pointer，bufLen uint32) {
destLen := uint32(unsafe.Sizeof(uint32(0)))
if bufLen < destLen{
fmt.Printf("error.
")
return
}
ptrb := (*uint32)(buf)
fmt.Printf("ptrb=%d", *ptrb)
}
```

```
**【错误示例】**

```
```
func main() {
var ptra = new(uint8)
*ptra = 1
fmt.Printf("ptra=%d
", *ptra)
foo(unsafe.Pointer(ptra))
}
func foo(buf unsafe.Pointer) {
// 指针类型变大，输出类型将显示非法区域内容，
// 若转换后的类型过大，并对其进行输入会造成对溢出漏洞
ptrb := (*uint32)(buf)
fmt.Printf("ptrb=%d", *ptrb)
}
```

```
**【修复建议】**

1、正确转换unsafe.Pointer类型指针到目标类型。

2、uintptr进行指针偏移运算不应超出其指向的内存边界（缓冲区边界），以确保后续使用unsafe.Pointer解引用读写目标值不被溢出。-------------参考华为go语言安全编程规范2.1
