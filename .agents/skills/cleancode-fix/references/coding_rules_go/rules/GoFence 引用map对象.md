# GoFence 引用map对象

- **规则ID**：7353400a-015e-4ba5-9e97-22b8ad714ba7
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

若通过map中不存在的key来取值，会得到该map中value类型对应的零值。 因此，应使用多重赋值来分辨key不存在的情况，即`"comma ok"`的方式判断是否正确获取到value

**【正确示例】**

```
```
type (
	age   uint
	name  string
	class map[name]age
)

func (c class) getAge(name name) age {
	return c[name] 
}
func (c class) averagegood(students []name) (float32, error) {
	cnt := 0
	sum := age(0)
	for _, student := range students {
		if studentAge, ok := c[student]; !ok { // 正确：判断对应的key值是否存在
			continue
		} else {
			sum += studentAge
			cnt++
		}
	}
	if cnt == 0 {
		return 0, errors.New("input is empty or not found")
	}
	return float32(sum) / float32(cnt), nil
}
```

```
**【错误示例】**

```
```
type (
	age   uint
	name  string
	class map[name]age
)

func (c class) getAge(name name) age {
	return c[name] //错误： 这里如果查找失败，缺省会返回0，造成外部计算错误
}

// average 计算输入学生的平均年龄
func (c class) averagebd(students []name) (float32, error) {
	if len(students) == 0 {
		return 0, errors.New("input is empty")
	}
	sum := age(0)
	for _, student := range students {
		sum += c.getAge(student)
	}
	return float32(sum) / float32(len(students)), nil
}
```

```
**【修复建议】**

引用前，进行非空的判断--------参考华为go语言编程规范3.1
