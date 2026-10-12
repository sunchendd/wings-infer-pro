# G.CMT.01 public或protected修饰的元素应添加Javadoc注释

- **规则ID**：22e8c970-2ccf-40cf-90af-238cf87ef637
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

最低限度要为每个public或protected修饰的类、接口、枚举、类方法和类属性添加注释，这些注释的格式应该采用Javadoc注释格式（即使用`/** */`进行注释），除此之外按需添加Javadoc注释。实现接口方法时，其Javadoc允许使用{@inheritDoc}。

**【正确示例】**

```
##### 场景1：
- 修复示例：

```java
// 【GOOD】public或protected修饰的元素应添加Javadoc注释
/**
 * doSomething方法的功能说明
 *
 * @param data xxx（data的具体含义）
 * @return List  返回结果集合，集合不会为null
 * @throws IOException 当出现xx时，会抛出IOException 
 */
public static List<String> doSomething(int data) throws IOException {
    ...
}
```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：

```java
// 【不符合】未添加注释
public static List<String> doSomething(int data) throws IOException {
    ...
}
 ```


```
**【修复建议】**

为public或protected修饰的元素应添加Javadoc注释。

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
