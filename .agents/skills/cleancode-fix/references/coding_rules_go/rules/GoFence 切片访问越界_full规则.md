# GoFence 切片访问越界_full规则

- **规则ID**：7185d132-31bc-4214-912c-05489d6b69fb
- **更新时间**：2026-04-07 04:20:00

---

**【问题级别】**

一般

**【描述】**

如果函数和方法是公开的（API）、有时甚至是内部的函数和方法，当需使用它的参数索引数组和切片时（数组、切片可以是全局的、或内部的、甚至传入的数组和切片），应确保此参数在合法索引的范围，不会导致越界。此类参数必须通过if等语句加以判断，不满足合法索引范围时返回错误，或不执行相应的操作，或返回合理的结果

**【正确示例】**

```
```
func Testoutgood() {
	arr, num := Testmakearr() // len = 9
	if num-1 > len(arr) {
		return //错误处理，防止出现切片越界错误
	} else {
		arr[num-2] = ""
		fmt.Print("balala")
	}
}
func Testmakearr() ([]string, int) {
	arr := make([]string, 8)
	return arr, 9
}
```

```
**【错误示例】**

```
```
func Testoutbad() {
	arr, num := Testmakearr()
	arr[num-1] = "" //error
}
func Testmakearr() ([]string, int) {
	arr := make([]string, 8)
	return arr, 9
}
```

```
**【修复建议】**

对从外部输入或计算的值，如需要用于切片索引，必须确保此值的范围在切片的索引范围内

代入并验证循环边界的范围，以保证不越界访问切片。---------------------------------参考华为go语言编程规范3.1
