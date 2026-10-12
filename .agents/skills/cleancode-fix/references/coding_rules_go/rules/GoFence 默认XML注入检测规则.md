# GoFence 默认XML注入检测规则

- **规则ID**：22401668-833a-4f8d-8ef2-cc3de4c42917
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

一般

**【描述】**

使用未经校验数据来构造XML会导致XML注入漏洞。如果用户被允许输入结构化的XML片段，则他可以在XML的数据域中注入XML标签来改写目标XML文档的结构和内容，XML解析器会对注入的标签进行识别和解释，引起注入问题

**【正确示例】**

```
```
type Array struct {
	A []Account `xml:"account"`
}
type Account struct {
	Id       int    `xml:"id"`
	Name     string `xml:"name"`
	Password string `xml:"password"`
}

func XMLInjectByUnmarshalgood(inject string) {
	var input = `
<?xml version="1.0"?>
<A>
<account>
	<id>1</id>
	<name>admin</name>
	<password>%s</password>
</account>
</A>
`
	inject = "123456</password></account><account><id>20</id><name>root</name><password>222222"//外部信息传入的信息
	s := fmt.Sprintf(input, inject)
	s = input + inject
	s = cleanXmlInjection(s)  //对外部信息进行相关检测处理，防止注危险
	s = input + inject
	fmt.Println("解析前：", s)
	var a Array
	err := xml.Unmarshal([]byte(s), &a)
	if err != nil {
		fmt.Println(err)
		return
	}
	fmt.Println("解析后：", a)
}

func cleanXmlInjection(s string) string {
	return s
}
```

```
**【错误示例】**

```
```
type Array struct {
	A []Account `xml:"account"`
}
type Account struct {
	Id       int    `xml:"id"`
	Name     string `xml:"name"`
	Password string `xml:"password"`
}

func XMLInjectByUnmarshalbad(inject string) {
	var input = `
<?xml version="1.0"?>
<A>
<account>
    <id>1</id>
    <name>admin</name>
    <password>%s</password>
</account>
</A>
`
	s := input + inject
	fmt.Println("解析前：", s)
	var a Array
	err := xml.Unmarshal([]byte(s), &a) //error
	if err != nil {
		fmt.Println(err)
		return
	}
	fmt.Println("解析后：", a)
}
```

```
**【修复建议】**

对有改变XML结构的特殊输入进行过滤验证或者编码；

对["&","<",">","'".'"',"/"]这些特殊字符过滤------------参考go语言Beego 框架之web安全
