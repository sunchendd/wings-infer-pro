# G.FIO.02 创建文件时必须显式指定合适的文件访问权限

- **规则ID**：3e929d2e-b1d6-42a8-8d0f-45886a9b680f
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

多用户的文件系统是通过权限和许可模型来保护文件访问的，多用户系统中的文件通常归属于某个特定的用户，该特定用户可以指定系统中的其他用户访问此文件内容。当一个文件被创建时，文件访问许可规定了哪些用户可以访问或者操作这个文件。



若文件创建时没有对文件的访问许可做足够的限制，攻击者便有机会对文件进行读取或者修改，因此一定要在创建文件时就为其指定访问许可，以防止未授权的文件访问。

**【正确示例】**

```
```
package main

import (    "fmt"

   "os" )

func main() {

   f, err := os.Create("/opt/pwm/limit.txt") // 缺省文件权限为0666

   if err != nil {

       fmt.Println("Create limit.txt file failure.")

       return

  }

   defer f.Close()

   f.Chmod(0600) // 【修改】使用Chmod()函数显式更改文件权限

   f.Write([]byte("This is a example."))

}
```

```
**【错误示例】**

```
```
package main

import (    "fmt"

   "os" )

func main() {

   // 【错误】没有显式指定文件权限

   f, err := os.Create("/opt/pwm/unlimit.txt")

   if err != nil {

       fmt.Println("Create unlimit.txt file failure.")

       return

  }

   defer f.Close()

   f.Write([]byte("This is a example."))

}
```

```
**【修复建议】**

多用户系统中创建文件时指定合适的权限
