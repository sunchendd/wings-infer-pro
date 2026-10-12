# GoFence 确保参与移位的操作数的位数足够

- **规则ID**：7ff4781c-fbb2-485e-b147-769e4e16bf58
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

一般

**【描述】**

移位的位数应该是无符号数。Go对无类型的常数依照参与表达式运算数据类型进行推导。进行移位操作时，自动推导出的类型宽度有可能小于实际对移位结果进行（比较）运算所要求的宽度。

**【正确示例】**

```
```
func foo(num uint16, bits uint8) bool {
    if uint32(num) > uint32(1)<<bits { // 这里类型强制转换后，应满足函数设计的要求
        return true
    }
    return false
}
func main() {
    fmt.Print(foo(65535, 16)) // 正确：返回false，65535 小于65536 （2^16）
}
```

```
**【错误示例】**

```
```
func foo(num uint16, bits uint8) bool {
	if num > (1 << bits) { // 错误：这里(1 << bits) 将被推导为uint16类型，可被移位操作回绕
		return true
	}
	return false
}
func main() {
	fmt.Print(foo(65535, 16)) // 错误：打印true，但65535 小于65536 （2^16）
}
```

```
**【修复建议】**

对数据进行类型转换--------------参考华为go语言编程规范2.1
