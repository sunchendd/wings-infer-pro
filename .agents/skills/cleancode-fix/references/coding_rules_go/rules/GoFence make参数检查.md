# GoFence make参数检查

- **规则ID**：a22baedd-3d38-43e1-925c-697f788bc89e
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

使用make创建slice、map、chan时，如果指定数组、slice、map、chan大小来自

于由外部输入，或由外部输入计算或推导出，或内部计算的大小参数可导致超出规则的大小限制，则必须对输入的整数参数值进行合法性校验，以防止输入的是负值或者超出系统可分配内存的最大值，引起系统退出或者系统崩溃，上述大小进行合法性校验，指的是 make slice的长度和容量参数、map的大小参数、chan的缓冲区大小。应确保满足：



1、大小值不是负数

2、如果make slice需要指定容量参数，容量值必须大于等于长度值

3、不超出程序需要解决问题的最大规模需求

**【正确示例】**

```
```
func TestAppendgood(arr []int) {
	if Checker(arr) { //添加验证
		arrLen := len(arr)
		arr2 := make([]int, arrLen+1, arrLen+1)
		arr2 = append(arr2, 1)
		_ = arr2[1:]
	}
}

const INT_MAX = int(^uint(0) >> 1)

func Checker(arr []int) bool {
	if len(arr)+1 < INT_MAX { //保证在实际操作中不超出业务所规定的范围大小
		return true
	} else {
		return false
	}
}
```

```
**【错误示例】**

```
```
func TestAppendbad(a int, arr []int) {
	arrLen := len(arr)
	arr2 := make([]int, arrLen+1, arrLen+1)
	arr2 = append(arr2, 1)
	_ = arr2[1:]
}
```

```
**【修复建议】**

在make初始化slice和map时，根据预估或校验范围的大小来申请合适的容量--------参考华为go语言安全编程规范2.1
