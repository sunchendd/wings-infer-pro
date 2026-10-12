# G.OBJ.07 子类覆写父类方法或实现接口时必须加上@Override注解

- **规则ID**：1ca51279-a5fb-4a20-9876-0ce7ffb8b12f
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

加上`@Override`注解的好处是，如果覆写时因为疏忽，导致子类方法的参数同父类不一致，编译时会报错，使问题在编译期就被发现；如果父类修改了方法定义造成子类不再覆写父类方法，也能使问题在编译期尽早被发现。

**【正确示例】**

```
##### 场景1：
- 修复示例： 

  ```java
    class BaseClass {
        public void doSomething() {
            ...
        }
    }

    class SubClass extends BaseClass {
        @Override
        public void doSomething() {
            ...
        }
    }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例： 

  ```java
    class BaseClass {
        public void doSomething() {
            ...
        }
    }

    class SubClass extends BaseClass {
        public void doSomething() {
            ...
        }
    }
  ```


```
**【修复建议】**

子类重载的父类方法，要添加@Override注解注解。

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
