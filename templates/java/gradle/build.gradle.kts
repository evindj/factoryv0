// Software-factory Java/Gradle baseline. `./gradlew check` = spotlessCheck + ErrorProne/NullAway + tests + coverage.
import net.ltgt.gradle.errorprone.CheckSeverity
import net.ltgt.gradle.errorprone.errorprone

plugins {
    java
    jacoco
    id("com.diffplug.spotless") version "7.0.2"
    id("net.ltgt.errorprone") version "4.1.0"
    id("info.solidsoft.pitest") version "1.15.0"
}

group = "com.example"
version = "0.1.0-SNAPSHOT"
val basePackage = "com.example"

java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }

repositories { mavenCentral() }

dependencies {
    errorprone("com.google.errorprone:error_prone_core:2.36.0")
    errorprone("com.uber.nullaway:nullaway:0.12.3")
    testImplementation(platform("org.junit:junit-bom:5.11.4"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
    testImplementation("org.assertj:assertj-core:3.27.3")
    testImplementation("net.jqwik:jqwik:1.9.2")
    testImplementation("com.tngtech.archunit:archunit-junit5:1.4.0")
}

tasks.withType<JavaCompile>().configureEach {
    options.compilerArgs.addAll(listOf("-Xlint:all", "-Werror"))
    options.errorprone {
        disableWarningsInGeneratedCode = true
        check("NullAway", CheckSeverity.ERROR)
        option("NullAway:AnnotatedPackages", basePackage)
    }
}

tasks.test {
    useJUnitPlatform { includeEngines("junit-jupiter", "jqwik") }
    finalizedBy(tasks.jacocoTestReport)
}

tasks.jacocoTestCoverageVerification {
    violationRules { rule { limit { counter = "BRANCH"; minimum = "0.80".toBigDecimal() } } }
}

tasks.check { dependsOn(tasks.jacocoTestCoverageVerification) }

spotless {
    java {
        googleJavaFormat()
        removeUnusedImports()
    }
}

// Mutation testing (evidence stage): ./gradlew pitest
pitest {
    junit5PluginVersion = "1.2.1"
    targetClasses = setOf("$basePackage.*")
    mutators = setOf("STRONGER")
    timestampedReports = false
}
