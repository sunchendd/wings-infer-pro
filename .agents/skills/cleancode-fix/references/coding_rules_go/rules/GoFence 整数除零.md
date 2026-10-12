# GoFence 整数除零

- **规则ID**：d6bde770-dbd4-4c9a-9843-221c3fd12b06
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

对整数做**除法**、**取模**、**取余**数操作时，除数或者模为0（下面统一称除数为零），将导致系统抛出异常。除非有默认的恢复机制，否则将导致无法继续当前的操作或任务

**【正确示例】**

```
```
import "fmt"
func testDivideByVar(divisor int) {
	d := divisor
	r := 100 / d
	fmt.Println(r)
}
func getZero() int {
	return 0
}
func testDivisorByReturngood() {
	zero := getZero()
	if zero != 0 {  //增加除数是否为0的判断
		r := 100 / zero
		fmt.Println(r)
		testDivideByVar(zero)
	} else {
		fmt.Println("kj=", zero)
	}

}
```

```
**【错误示例】**

```
```
import "fmt"
func testDivideByVar(divisor int) {
	d := divisor
	r := 100 / d
	fmt.Println(r)
}
func getZero() int {
	return 0
}
func testDivisorByReturn() {
	zero := getZero()
	r := 100 / zero       // issue1
	testDivideByVar(zero) // issue 2
	fmt.Println(r)
}
```

```
**【修复建议】**

不能确定除数不为零时，使用条件判断排除除数为零的情况。------------------参考华为go语言编程规范3.1
