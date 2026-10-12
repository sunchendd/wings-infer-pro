# G.FIO.04 确保安全地从压缩包中提取文件

- **规则ID**：f0a34dde-a72e-4236-a350-ce8953cc3733
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

解压文件时，提取出的文件标准路径落在解压目标目录之外：攻击者可以从zip文件中往用户可访问的任何目录写入任意的数据。

提取出的文件消耗过多的系统资源：当资源使用远远大于输入数据所使用的资源时，可能会发生DoS攻击。就ZIP算法的本质而言就可能导致ZIP炸弹的出现，因为极高的压缩率，即便在解压小文件时（如ZIP、GIF、以及gzip编码的HTTP内容），也可能会导致过度的资源消耗。

**【正确示例】**

```
##### 场景1：未校验文件数量、文件大小
- 修复示例：

```go
func Unsafe_Unzip_good1(m *BadCase.MyError) {
    r, err := zip.OpenReader("/user/demo/demo.zip")
    if err != nil {
        fmt.Println("ziperr")
    }
    if len(r.File) > TooManyFiles { // 符合：校验文件数量
        fmt.Println("zip file is too big.")
        return
    }
    var total int64
    destPath := "C:/Users/ywx591438/Desktop/"
    if !strings.HasPrefix(destPath, "poi") {
        return
    }
    for _, f := range r.File {
        if f.UncompressedSize64 > TooBigSingleSize || total > TooBigTotalSize {  // 符合：校验文件大小
            return
        }
        rdz, err := f.Open()
        defer rdz.Close()
        if err != nil {
            return
        }
        if f.FileInfo().IsDir() {
            err := os.MkdirAll(destPath, f.Mode())
            if err != nil {
                return
            }
            continue
        }
        destFile, err := os.Create(destPath + "/" + f.Name)
        if err != nil {
            return
        }
        // 符合：io.CopyN 拷贝已知大小，防止数据被篡改
        wt, err := io.CopyN(destFile, rdz, int64(f.UncompressedSize64))
        if err != nil {
            return
        }
        total += wt
    }
}
```
##### 场景二：未校验文件的个数
- 修复示例：
```go
// 将要解压的zipfile文件的压缩包解压到destpath目的路径
// 在调用前，确保destpath是合法的（在允许应用&用户访问的目录范围内，而非外部恶意输入）
func unzipFileSafe(zipfile, destpath string) error {
    // 打开压缩包
    r, err := zip.OpenReader(zipfile)
    if err != nil {
        return errors.New("open the zipfile error")
    }
    defer r.Close()
    // 符合：增加解压文件的数量限制(最大为1024)，防止内存耗尽
    if len(r.File) > TooManyFiles {
        return errors.New("too many file will be unzip")
    }
    destpath = filepath.Clean(destpath) // 符合：将目的路径标准化
    var totalWrote int64
    // 遍历压缩包内的目录和文件
    for _, file := range r.File {
        rc, err := file.Open()
        if err != nil {
            err = errors.New("open file which in zip archive error")
            break
        }
        if file.UncompressedSize64 > TooBigSingleSize || totalWrote > TooBigTotalSize { // 符合：检查单个以及累积解压文件大小
            ... // error process
            // err = ...
            return err
        }
        // 拼装指定的解压路径
        var targetpath = filepath.Join(destpath, file.Name)
        if !strings.HasPrefix(targetpath, destpath) { // 符合：检查输出到目标路径
            ... // error process
            // err = ...
            return err
        }
        // 如果是目录则创建；如果是文件则把文件复制到指定的目的地
        if file.FileInfo().IsDir() {
            e := os.MkdirAll(targetpath, file.Mode())
            if e != nil {
                ... // error process
                // err = ...
                return err
            }
        } else {
            f, e := os.OpenFile(targetpath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, file.Mode())
            if e != nil {
                ... // error process
                err = errors.New("open the dest file error")
                break
            }
            // 从压缩流中把内容复制到目的文件中
            wt, e := io.CopyN(f, rc, int64(file.UncompressedSize64)) // 符合：io.CopyN 拷贝已知大小，防止数据被篡改
            if e != nil {
                ... // error process
                err = errors.New("copy file content error")
                break
            }
            totalWrote += wt
            fmt.Println("wt:", wt)
            f.Close()
        }
        rc.Close()
    }
    return err
}
```

```
**【错误示例】**

```
##### 场景1：未校验文件数量、文件大小
- 错误示例：

```go
func Unsafe_Unzip_bad1() {
    r, err := zip.OpenReader("/user/demo/demo.zip")
    if err != nil {
        fmt.Println("ziperr")
        return
    }
    if len(r.File) > TooManyFiles {
        fmt.Println("zip file is too big.")
        return
    }
    var total int64
    destPath := "/user/demo/"
    if !strings.HasPrefix(destPath, "poi") {
        return
    }
    for _, f := range r.File {
        rdz, err := f.Open()
        defer rdz.Close()
        if err != nil {
            return
        }
        if f.FileInfo().IsDir() {
            err := os.MkdirAll(destPath, f.Mode())
            if err != nil {
                return
            }
            continue
        }
        destFile, err := os.Create(destPath + "/" + f.Name)
        if err != nil {
            return
        }
        // 不符合: 未校验文件大小
        wt, err := io.Copy(destFile, rdz)

        if err != nil {
            return
        }
        total += wt
    }
}
```
##### 场景二：未校验文件的个数
- 错误示例：
```go
func Unsafe_Unzip_bad2() {
    // 不符合: 未校验文件的个数
    r, err := zip.OpenReader("/user/demo/demo.zip")
    if err != nil {
        fmt.Println("ziperr")
    }
    var total int64
    destPath := "/user/demo/"
    if !strings.HasPrefix(destPath, "poi") {
        return
    }
    for _, f := range r.File {
        if f.UncompressedSize64 > 100000 || total > 300000 {
            return
        }
        rdz, err := f.Open()
        defer rdz.Close()
        if err != nil {
            return
        }
        if f.FileInfo().IsDir() {
            err := os.MkdirAll(destPath, f.Mode())
            if err != nil {
                return
            }
            continue
        }
        destFile, err := os.Create(destPath + "/" + f.Name)
        if err != nil {
            return
        }
        wt, err := io.CopyN(destFile, rdz, int64(f.UncompressedSize64))
        if err != nil {
            return
        }
        total += wt
        }
    }
```

```
**【修复建议】**

为确保安全地从压缩包中提取文件，需执行以下操作：

1. 解压路径校验。

2. 校验文件数量、文件大小。
