# G.OTH.07 安全随机数生成器尽量复用

- **规则ID**：68f28635-6c7a-431a-bf91-048b9ac76630
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

提示

**【描述】**

Java中的SecureRandom是一种密码学安全的伪随机数产生器，对于使用非真随机数产生器产生随机数时，要使用少量真随机数作为种子。为了提升真随机数种子的利用效率，应避免每次创建的SecureRandom对象仅生成一次安全随机数：



很多情况下，频繁获取真随机数会导致阻塞，所以应该充分利用每次获取的真随机数作为种子，尽量多的产生安全随机数；



使用SecureRandom对象生成一次安全随机数，新生成的安全随机数的量可能小于其种子的量，伪随机数产生器完全失去其应有的价值。

**【正确示例】**

```
##### 场景1：
- 修复示例1：定义静态的安全随机数生成器对象，重复用来生成随机数

```java
// 【JDK 9+】 新增了标准的DRBG伪随机数产生器，包括HASH-DRBG、HMAC-DRBG、CTR-DRBG三种。
private static SecureRandom randomInstance; // 使用‘静态代码块’进行初始化
static {
    try {
        randomInstance = SecureRandom.getInstance("DRBG", DrbgParameters.instantiation(256, RESEED_ONLY, null));
    } catch (NoSuchAlgorithmException e) {
        throw new RuntimeException(e);
    }
}

public void doSomething() {
    byte[] salt = new byte[16];
    randomInstance.nextBytes(salt);
    ...
}
```
- 修复示例2：定义静态的安全随机数生成器对象，重复用来生成随机数

```java
private static final SecureRandom random; // 使用‘静态代码块’进行初始化
static {
    try {
        random = SecureRandom.getInstanceStrong();
    } catch (NoSuchAlgorithmException e) {
        throw new RuntimeException(e);
    }
}

public void doSomething() {
    byte[] salt = new byte[16];
    random.nextBytes(salt);
    ...
}
```

```
**【错误示例】**

```
##### 场景1：
- 错误示例1：每次新建的安全随机数生成器只生成一次随机数。

```java
public void doSomething() {
    /* 不符合: 每次新建的安全随机数生成器只生成一次随机数。 */
    byte[] salt = new byte[16];
    SecureRandom random = SecureRandom.getInstance(...);
    random.nextBytes(salt);
	...
}
```

```
**【修复建议】**

建议对安全随机数进行复用
