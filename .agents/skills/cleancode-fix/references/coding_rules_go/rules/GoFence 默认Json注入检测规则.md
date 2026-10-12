# GoFence 默认Json注入检测规则

- **规则ID**：f0f5b7fc-a9ed-4465-9ca8-cc65743db4d9
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

一般

**【描述】**

我们知道JSON是根据引号（"）、冒号(：）区分各字符的意义的。如果有恶意用户向JSON中注入恶意字符，那么JSON将解析失败。

**【正确示例】**

```
```
type Person struct {
	Id       int
	Role     string
	Password string
}
func JsonUnmarshalgood(data []byte) error {
	var persons Person
	err := json.Unmarshal(data, &persons) // ok
	if err != nil {
		fmt.Println("error:", err)
	}
	fmt.Println("解析后：", persons)
	return err
}

func JsonHandle(inject string) error {
	data, err := json.Marshal(&Person{
		Id:       1,
		Role:     "guest",
		Password: inject,
	})
	if err != nil {
		fmt.Println("error:", err)
		return err
	}
	fmt.Println(string(data))
	err = JsonUnmarshalgood(data)
	return err
}
```

```
**【错误示例】**

```
```
type Person struct {
	Id       int
	Role     string
	Password string
}

func JsonInjectByMarshalbad(inject string) {
	var input = `[
    {"id": 1, "Role": "guest", "password": "s"}]`
	s := fmt.Sprintf(input, inject) //错误：外部输入未进行校验
	var persons []Person
	err := json.Unmarshal([]byte(s), &persons) // error
	if err != nil {
		fmt.Println("error:", err)
	}
	fmt.Println("解析后：", persons)
}
```

```
**【修复建议】**

只需要对其关键字符进行转义即可，字符串中的 “ 同样需要转义

外部输入进行有效验证，防止数据注入问题-----参考go分析与 安全测试
