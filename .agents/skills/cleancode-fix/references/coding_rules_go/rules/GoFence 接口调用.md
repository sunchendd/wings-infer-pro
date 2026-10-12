# GoFence 接口调用

- **规则ID**：8a07f0c7-5b43-4d85-828e-0d10eff74e7c
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

在go语言的底层，interface类型定义的变量（接口变量）有两个成员变量，一个类型和一个值，只有两个都为nil的这个接口变量才是nil，但是如果某个具体的对象赋值给接口变量，无论赋值的对象是不是nil，这个接口变量都不可能是nil。因此不应将存在类型的nil赋值给接口变量

**【正确示例】**

```
type tiContainer interface {
	CreateProcess() (tiProcess, error)
}
type tinContainer struct {
	sync.Mutex
	hcsContainer tiContainer
}
type tiProcess interface {
	Pid() int
	ExitCode() (int, error)
}
type tiiClient struct {
	sync.Mutex
}
type tiiProcess struct {
	id         string
	pid        int
	hcsProcess tiProcess
}

func (c *tiiClient) getContainer() *tinContainer {
	return &tinContainer{}
}
func (c *tiiClient) Start() (int, error) {
	ctr := c.getContainer()

	if ctr.hcsContainer != nil {  //添加判断条件，防止空指针引用
		newProcess, _ := ctr.hcsContainer.CreateProcess() 
		p := &tiiProcess{
			hcsProcess: newProcess,
			id:         "init",
			pid:        newProcess.Pid(),
		}
		func() {
			Pid := uint32(p.pid)
			_ = Pid
		}()
	}
	return 0, nil
}

```
**【错误示例】**

```
type tiContainer interface {
	CreateProcess() (tiProcess, error)
}
type tinContainer struct {
	sync.Mutex
	hcsContainer tiContainer
}
type tiProcess interface {
	Pid() int
	ExitCode() (int, error)
}
type tiiClient struct {
	sync.Mutex
}
type tiiProcess struct {
	id         string
	pid        int
	hcsProcess tiProcess
}

func (c *tiiClient) getContainer() *tinContainer {
	return &tinContainer{}
}
func (c *tiiClient) Start() (int, error) {
	ctr := c.getContainer()

		newProcess, _ := ctr.hcsContainer.CreateProcess() // issue：ctr.hcsContainer=nil
		p := &tiiProcess{
			hcsProcess: newProcess,
			id:         "init",
			pid:        newProcess.Pid(),
		}
		func() {
			Pid := uint32(p.pid)
			_ = Pid
		}()
	return 0, nil
}

```
**【修复建议】**

确保赋值给接口变量的对象指针有效，否则应赋予无类型的nil值

必须使用error作为函数的错误返回值类型, 对非错误必须返回无类型的nil

---------------参考华为go语言编程规范3.1
