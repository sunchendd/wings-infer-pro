# GoFence 敏感信息打印

- **规则ID**：68e648ae-df7b-4d80-a67c-6972e650a7dc
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

一般

**【描述】**

敏感数据传输过程中要防止窃取和恶意篡改。使用安全的加密算法加密传输对象可以保护数据，防止对象被非法篡改，保持其完整性。在以下场景中，需要对对象密封和数字签名来保证数据安全：

1、序列化或者传输敏感数据

2、没有使用类似SSL传输通道

3、敏感数据需要长久保存，比如在硬盘驱动器上

**【正确示例】**

```
```
type User struct {
    userName   string
    password   string
    PassCount  string
    testNoPass string
    addr       *Addr
}
type Addr struct {
    info string
}

type T struct {
    a string
    b string
}

func Printxf(p1 string) {
}

func TestEntryPoint2(pwd1 string) {
    t := &T{}
    t.a = pwd1
    testEntryPointM1(t)
}

func testEntryPointM1(t *T) {
    testEntryPointM2(t.a)
}

func testEntryPointM2(str string) {
    u := &User{}
    u.password = str
    test22(u)
}
func test22(user *User) {

    Printxf(user.userName) //ok
}
func doSink(para string) {
    Printxf(para)
}
```

```
**【错误示例】**

```
```
type User struct {
    userName   string
    password   string
    PassCount  string
    testNoPass string
    addr       *Addr
}

type Addr struct {
    info string
}
func Printxf(p1 string) {
}

func (u *User) GetPassword() string {
    tmpRet := u.password
    return tmpRet
}

func TestReturnSource(u *User) {
    param := u.GetPassword()
    doSink(param)
}

func doSink(para string) {
    Printxf(para) //error, Do not print pwd information.
}
```

```
**【修复建议】**

需要对对象密封和数字签名来保证数据安全-------参考华为go语言安全编程规范2.1
