# G.MEM.01 禁止解引用空指针

- **规则ID**：3bb9cbd6-997c-4319-826c-5e066df7bb65
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

指针变量使用前需要校验是否非`nil`，防止解引用空指针问题。

**【正确示例】**

```
##### 场景1：解引用空指针
- 修复示例：

```go
type Student struct {
    Name string
    Age int
}

func (s *Student) Foo(){
    fmt.Printf("Student: name=%s, age=%d 
", s.Name, s.Age)
}

func main() {
    var s *Student
    if len(os.Args) > 1 {
        s = &Student{Name:"test", Age:10}
    }
    if s == nil { // 增加判空处理
        fmt.Println("Failed.")
        return
    }
    s.Foo()  // 符合：使用s变量前，做了空指针判断
}
```

```
**【错误示例】**

```
##### 场景1：解引用空指针
- 错误示例：

```go
type Student struct {
    Name string
    Age int
}

func (s *Student) Foo(){
    fmt.Printf("Student: name=%s, age=%d 
", s.Name, s.Age)
}

func main() {
    var s *Student // 声明后默认值是nil
    if len(os.Args) > 1 {
        s = &Student{Name:"test", Age:10}
    }
    s.Foo()  // 不符合：s可能为nil
}
```

```
**【修复建议】**

不解引用空指针：指针类型变量使用前进行校验。
