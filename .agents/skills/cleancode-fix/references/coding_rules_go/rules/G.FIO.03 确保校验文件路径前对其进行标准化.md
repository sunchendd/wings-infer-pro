# G.FIO.03 确保校验文件路径前对其进行标准化

- **规则ID**：e2c08617-c0b6-405a-b0aa-bcb1b229e1ed
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

外部文件路径不可信，如果未标准化外部文件路径，攻击者就有机会通过恶意构造文件路径进行文件的越权访问；如果不校验外部文件路径，可能造成系统文件的被任意访问，出现安全风险。

因此，外部文件路径使用前必须进行标准化并校验。

**【正确示例】**

```
##### 场景1：外部文件路径未标准化。
- 修复示例：

```go
// 验证文件路径是否在安全目录/opt/pwm下
func validate(path string) bool {
    relPath, err := filepath.Abs(path) // 符合：对文件路径进行标准化
    if err != nil {
        fmt.Println("It's error when converted to an absolute path.")
        return false
    }
    pattern := `^/opt/pwm`
    reg := regexp.MustCompile(pattern)
    return reg.MatchString(relPath) // 符合：使用标准化后的路径，进行正则匹配
}

func Standardized_Filepath_bad1() {
    var path string
    flag.StringVar(&path, "filepath", "", "Get user input file path")
    flag.Parse()
    // 在函数内路径先未标准化再校验
    if !validate(path) {
        fmt.Println("It's not validate path.")
    }
    file, err := os.Open(path)
    if err != nil {
        fmt.Println("It's error when converted to an absolute path.")
    }
    file.Close()
}
```

```
**【错误示例】**

```
##### 场景1：外部文件路径未标准化。
- 错误示例：

```go
func Standardized_Filepath_bad1() {
    var path string
    // 不符合: 未标准化路径
    flag.StringVar(&path, "filepath", "", "Get user input file path")
    flag.Parse()
    file, err := os.Open(path)
    if err != nil {
        fmt.Println("It's error when converted to an absolute path.")
    }
    file.Close()
}
```

```
**【修复建议】**

外部文件路径使用前，按顺序执行如下两个步骤：

**1、文件路径标准化**：例如使用filepath.Abs()函数返回绝对路径，删除了所有符号链接。

**2、文件路径校验**：针对标准化后的文件路径进行校验。常用的校验方式是保证操作的文件在预期目录下。
