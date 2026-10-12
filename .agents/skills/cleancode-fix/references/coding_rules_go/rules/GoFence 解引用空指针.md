# GoFence 解引用空指针

- **规则ID**：39119fdf-c178-4544-945a-8a2af2aa844d
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

Go语言中，对于非引用类型，声明即被默认初始化；对于引用类型，声明后其值是（nil）。使用引用类型变量前，必须对其有效构建并初始化好，以确保代码的控制逻辑中不存在导致引用空指针或使用未初始化变量的缺陷。

**【正确示例】**

```
```
type union struct {
	a *int
}

func (u *union) calculate() {
	m, t := getUnion()
	if t != nil {         //在指针引用前做判断
		u.uin(t, m)
	} else {
		fmt.Println("input t is nil")
	}

}
func (u *union) uin(t *union, m int) {
	if u.a != nil {          //在指针引用前做判断
		*u.a = *t.a + m
	} else {
		fmt.Println("u.a is nil")
	}
}
func getUnion() (magic int, u *union) {
	magic = 0
	u = &union{}
	a, p := getUnionInt(nil)
	u.a = p
	fmt.Println("u.a==", u.a) //u.a=nil
	if u.a != nil {           //在指针引用前做判断
		*u.a = a
	}
	return
}
func getUnionInt(a *int) (int, *int) {
	if a == nil {
		return 0, nil
	}
	return 100, new(int)
}
```

```
**【错误示例】**

```
```
type union struct {
    a *int
}

func (u *union) calculate() {
    m, t := getUnion()
    u.uin(t, m)
}
func (u *union) uin(t *union, m int) {
    *u.a = *t.a + m //error
}
func getUnion() (magic int, u *union) {
    magic = 0
    u = &union{}
    a, p := getUnionInt(nil)
    u.a = p
    *u.a = a //error
    return
}
func getUnionInt(a *int) (int, *int) {
    if a == nil {
        return 0, nil
    }
    return 100, new(int)
}
```

```
**【修复建议】**

在引入前，对指针进行非空的判断处理------------------参考华为go语言编程规范3.1
