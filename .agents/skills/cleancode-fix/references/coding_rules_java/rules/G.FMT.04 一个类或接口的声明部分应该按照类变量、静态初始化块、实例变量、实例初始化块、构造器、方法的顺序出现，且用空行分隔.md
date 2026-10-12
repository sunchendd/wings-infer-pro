# G.FMT.04 一个类或接口的声明部分应该按照类变量、静态初始化块、实例变量、实例初始化块、构造器、方法的顺序出现，且用空行分隔

- **规则ID**：bd6a5725-ca83-49f8-8bac-4cbc004b50fe
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

一个类或接口的声明部分应该按照以下顺序排列：



- 类（静态）变量

- 静态初始化块

- 实例变量

- 实例初始化块

- 构造器

- 方法或嵌套类，嵌套类可以与成员方法根据业务逻辑交替出现，把概念上相近的放在一起，无需把所有嵌套类都下移至文件底部

- 类（静态）变量、实例变量、构造器，均按访问修饰符从大到小排列：public、protected、package（default）、private



**说明：**



1. 对于自注释成员变量之间可以不加空行；

2. 非自注释成员变量应该加注释且成员变量间以空行分隔。

**【正确示例】**

```
##### 场景1：部分类声明未空行分隔
- 修复示例：

  ```java

  public class DeclarationOrder {
      private static final Logger LOGGER = LoggerFactory.getLogger(DeclarationOrder.class);
  
      static class StaticClass {
          ...
      }
      
      private void privateMethod() {
          ...
      }   
  ```


```
**【错误示例】**

```
##### 场景1：部分类声明未空行分隔
- 错误示例：

  ```java
  public class DeclarationOrder {
      private static final Logger LOGGER = LoggerFactory.getLogger(DeclarationOrder.class);

      private void privateMethod() {
          ...
      }   

      static class StaticClass {
          ...
      }

  }
  ```


```
**【修复建议】**

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
