# G.CMT.07 正式交付给客户的代码不应包含TODO/FIXME注释

- **规则ID**：2dbe1e26-6475-4ce2-a256-e9938eb224a2
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

TODO注释一般用来描述已知待改进、待补充的修改点。FIXME注释一般用来描述已知缺陷。在版本开发阶段可以使用这两类标签标注一些待处理的问题。



对于版本交付的代码中不应存在这两类标签，否则可能会被误解为代码中存在未实现的功能或已知的缺陷。

**【正确示例】**

```
##### 场景1：交付时文件中包含TODO/FIXME注释
- 修复示例：删除TODO、FIXME注释

  ```java
  public boolean doSomething(String data) {
      ...      
      return true;
  }
  ```


```
**【错误示例】**

```
##### 场景1：交付时文件中包含TODO/FIXME注释
- 错误示例：

  ```java
  // 【不符合】交付时文件中包含TODO/FIXME注释
  // TODO(<author-name>): 补充XX处理
  public boolean doSomething(String data) {
      ...
    
      // FIXME: 存在XX缺陷，需添加xxx实现代码
      ...
      return true;
  }
  ```


```
**【修复建议】**

正式交付的代码中，排查所有的TODO、FIXME注释，保证功能是完整的，已知缺陷都已经被修复，并将所有的TODO、FIXME注释删除。

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
