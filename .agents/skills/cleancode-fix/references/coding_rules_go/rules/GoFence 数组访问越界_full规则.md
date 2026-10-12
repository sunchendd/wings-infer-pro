# GoFence 数组访问越界_full规则

- **规则ID**：b8b4a0e3-2ce8-4051-8869-e93ed1a11420
- **更新时间**：2026-04-07 04:20:00

---

**【问题级别】**

一般

**【描述】**

如果函数和方法是公开的（API）、有时甚至是内部的函数和方法，当需使用它的参数索引数组和切片时（数组、切片可以是全局的、或内部的、甚至传入的数组和切片），应确保此参数在合法索引的范围，不会导致越界。此类参数必须通过if等语句加以判断，不满足合法索引范围时返回错误，或不执行相应的操作，或返回合理的结果。

**【正确示例】**

```
```
func SetBuffergood() {
	const BUFSIZ int = 5
	var buffer [BUFSIZ]byte
	var i = 0
	for i = 0; i < BUFSIZ; i++ { //BUFSIZ = 5 ; 需要满足 i < BUFSIZ-1
		if i < BUFSIZ-1 {
			buffer[i] = buffer[i+1]
		}
		fmt.Println(buffer[i])
	}
}
```

```
**【错误示例】**

```
```
func SetBufferbad() {
	const BUFSIZ int = 5
	var buffer [BUFSIZ]byte
	var i = 0
	for i = 0; i < BUFSIZ; i++ { // 错误：循环的上界可导致数组越界访问
		buffer[i] = buffer[i+1]
		fmt.Println(buffer[i])
	}
}
```

```
**【修复建议】**

对从外部输入或计算的值，如需要用于数组索引，必须确保此值的范围在数组的索引范围内

代入并验证循环边界的范围，以保证不越界访问数组。

---------------------------------参考华为go语言编程规范3.1
