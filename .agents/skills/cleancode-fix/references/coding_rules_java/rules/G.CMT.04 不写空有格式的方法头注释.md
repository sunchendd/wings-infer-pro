# G.CMT.04 不写空有格式的方法头注释

- **规则ID**：da824c7a-bea0-4b03-9622-77bcdd4d18b2
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

对于不需要添加注释的方法无需添加空有格式的注释，这样代码更整洁。

**【正确示例】**

```
##### 场景1：注释不够完整
- 修复示例：

  ```java
  // 【符合】注释信息完整
  
    /**
     * doSomething describe message
     *
     * @param str xxxx
     * @return List<String>  xxxx
     * @throws IOException xxxxx
     */
    private List<String> doSomething(String str) throws IOException {
        ...
    }
  ```


```
**【错误示例】**

```
##### 场景1：注释不够完整
- 错误示例：

  ```java
  // 【不符合】注释不够完整  
  /**
   *
   * @param str
   * @return
   * @throws IOException
   */
  public List<String> doSomething(String str) throws IOException {
      ...
  }
  ```


```
**【修复建议】**

注释中对方法的描述信息不能为空，且应该使用@param、@return、@throws注解分别对方法的参数、返回值、抛出的异常信息做描述。



对于不需要添加注释的方法，将空有格式的javadoc注释删除。

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
