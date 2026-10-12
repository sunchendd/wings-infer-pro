# G.PKG.04 导入的包按照稳定度排序

- **规则ID**：bc55d3b2-4f68-42fe-b756-84f6b1e7d635
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

使用标准的import顺序可增强可读性，建议的顺序：标准库，第三方库，本项目的库。

除了为使用cgo导入的“C”包外，应在一个import语句中导入所有需要的包并分组，不同的分组之间使用空行分割开。

**【正确示例】**

```
##### 场景1：导入包未按要求分组
- 修复示例：先用gofmt格式化文件，再按建议的顺序调整导入包顺序并分组。

  ```go
  import (  // 符合
      "fmt"
      "hash/adler32"
      "os"

      "github.com/foo/bar"
      "rsc.io/goversion/version"

      "project/foo"
      "project/user"
  )
  ```


```
**【错误示例】**

```
##### 场景1：导入包未按要求分组
- 错误示例：

  ```go
  import (  // 不符合
      "fmt"
      "hash/adler32"
      "os"
      "github.com/foo/bar"
      "rsc.io/goversion/version"
      "project/foo"
      "project/user"
  )
  ```


```
**【修复建议】**

先用gofmt格式化文件，再按建议的顺序调整导入包顺序并分组。

建议的顺序：标准库，第三方库，本项目的库。
